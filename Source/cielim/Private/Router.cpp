//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of FRouter.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "Router.h"

#include "CielimLoggingMacros.h"
#include "ZmqConnection/UCircularQueueData.h"

FRouter::FRouter(zmq::context_t &ContextPtr, const std::string &Address, CielimCircularQueue &CircularQueue)
{
	this->Context = &ContextPtr;

	this->RouterSocket = zmq::socket_t(ContextPtr, zmq::socket_type::router);
	this->RouterSocket.bind(Address.c_str());

	this->QueueSocket = zmq::socket_t(ContextPtr, zmq::socket_type::pair);
	this->QueueSocket.bind("inproc://OutboundQueueReady");

	// Monitor Router Socket for accepted connections and clean (or abrupt) disconnections
	zmq_socket_monitor(RouterSocket.handle(), "inproc://RouterSocketMonitor",
					   ZMQ_EVENT_ACCEPTED | ZMQ_EVENT_DISCONNECTED | ZMQ_EVENT_CLOSED);

	this->RouterMonitor = zmq::socket_t(ContextPtr, zmq::socket_type::pair);
	this->RouterMonitor.connect("inproc://RouterSocketMonitor");

	this->MultiThreadQueue = &CircularQueue;

	this->bContinueRun = true;

	UE_LOG(LogCielim, Display, TEXT("Router : Router bound to address: %hs"), Address.c_str());

	this->Thread = FRunnableThread::Create(this, TEXT("CielimRouterThread"));
}

void FRouter::Shutdown()
{
	if (!this->Thread)
		return;

	this->Stop();

	this->Thread->WaitForCompletion();

	delete this->Thread;
	this->Thread = nullptr;
}

bool FRouter::Init() { return true; }

uint32 FRouter::Run()
{
	while (this->bContinueRun)
	{
		zmq::pollitem_t PollItems[3] = {
			{static_cast<void *>(this->RouterMonitor), 0, ZMQ_POLLIN, 0},
			{static_cast<void *>(this->RouterSocket), 0, ZMQ_POLLIN, 0},
			{static_cast<void *>(this->QueueSocket), 0, ZMQ_POLLIN, 0},
		};

		// Poll with a timeout of 100ms

		const int NumEvents = zmq::poll(PollItems, 3, std::chrono::milliseconds(100));

		if (NumEvents < 0)
			continue;

		// Check for connections and disconnections
		if (PollItems[0].revents & ZMQ_POLLIN)
		{
			if (zmq::multipart_t Event; Event.recv(RouterMonitor))
			{
				zmq::message_t EventMessage = Event.pop();
				zmq::message_t EventAddress = Event.pop();

				// First two bytes of this are the event ID
				uint8 *EventData = EventMessage.data<uint8>();
				uint16 EventID = *reinterpret_cast<uint16 *>(EventData);

				// NOTE: This is the address of the server, not the client
				FString Address = FString(EventAddress.size(), EventAddress.data<char>());

				if (EventID == ZMQ_EVENT_ACCEPTED)
				{
					UE_LOG(LogCielim, Display, TEXT("Router : New connection accepted on %hs."),
						   TCHAR_TO_UTF8(*Address));
				}
				else if (EventID == ZMQ_EVENT_DISCONNECTED || EventID == ZMQ_EVENT_CLOSED)
				{
					UE_LOG(LogCielim, Display, TEXT("Router : Connection closed on %hs."), TCHAR_TO_UTF8(*Address));
				}
			}
		}
		// Check for incoming messages
		if (PollItems[1].revents & ZMQ_POLLIN)
		{
			if (zmq::multipart_t ReceiveMessage; ReceiveMessage.recv(RouterSocket))
			{
				// Incoming messages should be of the form: ID | (optional) delimiter | data

				if (ReceiveMessage.size() < 2)
				{
					UE_LOG(LogCielim, Warning, TEXT("Router : Message received was malformed; discarding."));
					continue;
				}

				zmq::message_t IDByteBlob = ReceiveMessage.pop();

				// IDs cannot be longer than 256 bytes long
				if (IDByteBlob.size() <= 0 || IDByteBlob.size() > 256)
				{
					UE_LOG(LogCielim, Warning, TEXT("Router : ID of client was malformed; discarding."));
					continue;
				}

				TArray<uint8> ID;
				ID.Append(IDByteBlob.data<uint8>(), IDByteBlob.size());

				FString IDStr = IDConvertToString(ID);

				UE_LOG(LogCielim, Display, TEXT("Router : Message received from client %hs."), TCHAR_TO_UTF8(*IDStr));

				bool bUseDelim = false;

				// Message may or may not include empty delimiter depending on client type
				if (ReceiveMessage.front().size() == 0)
				{
					bUseDelim = true;
					ReceiveMessage.pop();
				}

				// Send return message

				zmq::multipart_t ReturnMessage;

				ReturnMessage.add(std::move(IDByteBlob));
				if (bUseDelim)
					ReturnMessage.addstr("");

				FCircularQueueData ReturnData;

				ReturnData.ID = ID;
				ReturnData.bUseDelim = bUseDelim;

				ParseMessageAndSend(ReceiveMessage, ReturnMessage, ReturnData);
			}
		}
		// Check for outgoing messages
		if (PollItems[2].revents & ZMQ_POLLIN)
		{
			if (zmq::message_t Signal; QueueSocket.recv(Signal, zmq::recv_flags::none))
			{
				UE_LOG(LogCielim, Display, TEXT("Router : Outbound signal received."));

				if (!MultiThreadQueue->Responses.IsEmpty())
				{
					FCircularQueueData Data;
					MultiThreadQueue->Responses.Dequeue(Data);

					FString IDStr = IDConvertToString(Data.ID);

					UE_LOG(LogCielim, Display, TEXT("Router : Dequeued data for client %hs."), TCHAR_TO_UTF8(*IDStr));

					// Send return message

					zmq::multipart_t ReturnMessage;

					zmq::message_t IDByteBlob(Data.ID.GetData(), Data.ID.Num());

					ReturnMessage.add(std::move(IDByteBlob));
					if (Data.bUseDelim)
						ReturnMessage.addstr("");

					ParseCircularQueueDataAndSend(Data, ReturnMessage);
				}
			}
		}
	}

	return 0;
}

FString FRouter::IDConvertToString(const TArray<uint8> &ID)
{
	FString IDStr;

	bool IsReadable = true;

	for (const uint8 B : ID)
	{
		// This is the printable ASCII range
		if (B < 0x20 || B > 0x7E)
		{
			IsReadable = false;
			break;
		}
	}

	if (IsReadable)
	{
		IDStr.Reserve(ID.Num());

		for (const uint8 B : ID)
		{
			IDStr.AppendChar(B);
		}
	}
	else
	{
		// Set the string to hex digits if ID isn't printable
		IDStr = BytesToHex(ID.GetData(), ID.Num());
	}

	return IDStr;
}

void FRouter::ParseMessageAndSend(zmq::multipart_t &Message, zmq::multipart_t &ReturnMessage,
								  FCircularQueueData &ReturnData)
{
	UE_LOG(LogCielim, Display, TEXT("Router::ParseMessage"));

	const std::string Command = Message.popstr();

	UE_LOG(LogCielim, Display, TEXT("Basilisk command: %hs"), Command.c_str());

	if (Command == "PING")
	{
		ReturnMessage.addstr("PONG");
		ReturnMessage.send(RouterSocket);
	}
	else if (Command == "INIT_SCENE")
	{
		ReturnData.query = CommandType::INIT_SCENE;

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue INIT_SCENE..."));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(ReturnData);
		}

		ReturnMessage.addstr("OK");
		ReturnMessage.send(RouterSocket);
	}
	else if (Command == "SIM_UPDATE")
	{
		ReturnData.query = CommandType::SIM_UPDATE;

		ReturnData.payload.Emplace<FUpdatePayload>(FUpdatePayload());
		ReturnData.payload.Get<FUpdatePayload>().message = FCielimMessage();

		// @TODO: fix this message parsing. It's a mad hack!
		ReturnData.payload.Get<FUpdatePayload>().message.GetMessageModifiable().ParseFromArray(
			Message[2].data(), Message[2].size() * sizeof(char));

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue SIM_UPDATE..."));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(ReturnData);
		}

		ReturnMessage.addstr("OK");
		ReturnMessage.send(RouterSocket);
	}
	else if (Command == "REQUEST_IMAGE")
	{
		ReturnData.query = CommandType::REQUEST_IMAGE;

		uint32_t CameraID = -1;
		CameraID = std::stoi(Message.popstr());

		UE_LOG(LogCielim, Display, TEXT("Camera ID: %d"), CameraID);

		ReturnData.payload.Emplace<FImagePayload>(FImagePayload());
		ReturnData.payload.Get<FImagePayload>().shouldReturnImage = static_cast<bool>(std::stoi(Message.popstr()));

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue REQUEST_IMAGE"));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(ReturnData);
		}
	}
	else
	{
		ReturnMessage.addstr("ERROR");
		ReturnMessage.send(RouterSocket);
	}
}

void FRouter::ParseCircularQueueDataAndSend(FCircularQueueData &Data, zmq::multipart_t &ReturnMessage)
{
	UE_LOG(LogCielim, Display, TEXT("Router::ParseCircularQueue"));

	const CommandType Command = Data.query;

	if (Command == CommandType::REQUEST_IMAGE)
	{
		UE_LOG(LogCielim, Display, TEXT("Response to REQUEST_IMAGE received"));

		TArray64<uint8> ResponseImage;

		auto *TempPayload = Data.payload.TryGet<FImagePayload>();

		if (TempPayload != nullptr)
		{
			ResponseImage = TempPayload->image_data;

			UE_LOG(LogCielim, Display, TEXT("Image data was not NULL"));
		}

		const auto Bytes = sizeof(ResponseImage[0]) * ResponseImage.Num();

		ReturnMessage.addmem(ResponseImage.GetData(), Bytes);
		ReturnMessage.addtyp(Bytes);

		if (TempPayload != nullptr && TempPayload->centerOfBrightness.IsSet())
		{
			ReturnMessage.addtyp<double>(TempPayload->centerOfBrightness.GetValue().X);
			ReturnMessage.addtyp<double>(TempPayload->centerOfBrightness.GetValue().Y);
		}
		else
		{
			ReturnMessage.addmem(nullptr, 0);
			ReturnMessage.addmem(nullptr, 0);
		}
	}
	else
	{
		ReturnMessage.addstr("ERROR");
	}

	ReturnMessage.send(RouterSocket);
}

void FRouter::Stop() { this->bContinueRun = false; }

void FRouter::Exit()
{
	// Do nothing for now (called when Run() ends)
}
