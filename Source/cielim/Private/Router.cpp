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

	this->MultiThreadQueue = &CircularQueue;

	this->bContinueRun = true;

	this->RouterSocket.bind(Address.c_str());

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
		zmq::pollitem_t PollItems[1] = {
			{static_cast<void *>(this->RouterSocket), 0, ZMQ_POLLIN, 0},
		};

		// Poll with a timeout of 100ms

		const int NumEvents = zmq::poll(PollItems, 1, std::chrono::milliseconds(100));

		if (NumEvents < 0)
			continue;

		if (PollItems[0].revents & ZMQ_POLLIN)
		{
			zmq::multipart_t ReceiveMessage;

			if (ReceiveMessage.recv(this->RouterSocket))
			{
				if (ReceiveMessage.size() < 2)
				{
					UE_LOG(LogCielim, Warning, TEXT("Router : Message received was malformed; discarding."));
					continue;
				}

				std::string ID = ReceiveMessage.popstr();

				UE_LOG(LogCielim, Display, TEXT("Router : Message received from client %hs."), ID.c_str());

				bool bUseDelim = false;

				// Message may or may not include empty delimiter depending on client type
				if (ReceiveMessage.front().size() == 0)
				{
					bUseDelim = true;
					ReceiveMessage.pop();
				}

				// Send return message

				zmq::multipart_t ReturnMessage;

				ReturnMessage.addstr(ID);
				if (bUseDelim)
					ReturnMessage.addstr("");

				ParseMessage(ReceiveMessage, ReturnMessage);

				ReturnMessage.send(this->RouterSocket);
			}
		}
	}

	return 0;
}

void FRouter::ParseMessage(zmq::multipart_t &Message, zmq::multipart_t &ReturnMessage) const
{
	UE_LOG(LogCielim, Display, TEXT("Router::ParseMessage"));

	const std::string Command = Message.popstr();

	UE_LOG(LogCielim, Display, TEXT("Basilisk command: %hs"), Command.c_str());

	if (Command == "PING")
	{
		ReturnMessage.addstr("PONG");
	}
	else if (Command == "INIT_SCENE")
	{
		FCircularQueueData Data;
		Data.query = CommandType::INIT_SCENE;

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue INIT_SCENE..."));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Data);
		}

		ReturnMessage.addstr("OK");
	}
	else if (Command == "SIM_UPDATE")
	{
		FCircularQueueData Data;
		Data.payload.Emplace<FUpdatePayload>(FUpdatePayload());

		Data.query = CommandType::SIM_UPDATE;
		Data.payload.Get<FUpdatePayload>().message = FCielimMessage();

		// @TODO: fix this message parsing. It's a mad hack!
		Data.payload.Get<FUpdatePayload>().message.GetMessageModifiable().ParseFromArray(
			Message[2].data(), Message[2].size() * sizeof(char));

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue SIM_UPDATE..."));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Data);
		}

		ReturnMessage.addstr("OK");
	}
	else if (Command == "REQUEST_IMAGE")
	{
		uint32_t CameraID = -1;
		CameraID = std::stoi(Message.popstr());

		UE_LOG(LogCielim, Display, TEXT("Camera ID: %d"), CameraID);

		// A request is received and is put in the queue to be handled by the main (game) thread
		FCircularQueueData Request;

		Request.query = CommandType::REQUEST_IMAGE;
		Request.payload.Emplace<FImagePayload>(FImagePayload());
		Request.payload.Get<FImagePayload>().shouldReturnImage = (bool)std::stoi(Message.popstr());

		UE_LOG(LogCielim, Display, TEXT("Waiting to enqueue REQUEST_IMAGE"));

		bool EnqueueResult = false;
		while (!EnqueueResult)
		{
			EnqueueResult = this->MultiThreadQueue->Requests.Enqueue(Request);
		}

		// Loop until we get the response from the main (game) thread
		FCircularQueueData Response;

		UE_LOG(LogCielim, Display, TEXT("Waiting for reposnse to REQUEST_IMAGE"));

		bool DequeueResult = false;
		while (!DequeueResult)
		{
			// I can call this directly so the thread blocks on the image return.
			// This assumes that the next item placed in the queue is the image response.
			DequeueResult = this->MultiThreadQueue->Responses.Dequeue(Response);
		}

		UE_LOG(LogCielim, Display, TEXT("Reposnse to REQUEST_IMAGE received"));

		TArray64<uint8> ResponseImage;

		auto *TempPayload = Response.payload.TryGet<FImagePayload>();

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
}

void FRouter::Stop() { this->bContinueRun = false; }

void FRouter::Exit()
{
	// Do nothing for now (called when Run() ends)
}
