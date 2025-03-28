#include "Router.h"

#include "CielimLoggingMacros.h"

FRouter::FRouter(zmq::context_t& ContextPtr, const std::string& Address)
{
    this->Context = &ContextPtr;
    this->RouterSocket = zmq::socket_t(ContextPtr, zmq::socket_type::router);

    this->bContinueRun = true;

    this->RouterSocket.bind(Address.c_str());

    UE_LOG(LogCielim, Display, TEXT("Router : Router bound to address: %hs"), Address.c_str());

    this->Thread = FRunnableThread::Create(this, TEXT("CielimRouterThread"));
}

FRouter::~FRouter()
{
    if (!this->Thread)
        return;

    this->Thread->Kill();

    this->Thread->WaitForCompletion();

    delete this->Thread;
    this->Thread = nullptr;
}

bool FRouter::Init()
{
    return true;
}
    
uint32 FRouter::Run()
{
    while (this->bContinueRun)
    {
        zmq::pollitem_t PollItems[1] =
        {
            {static_cast<void*>(this->RouterSocket), 0, ZMQ_POLLIN, 0},
        };

        // Poll with a timeout of 100ms

        const int NumEvents = zmq::poll(PollItems, 1, std::chrono::milliseconds(100));

        if (NumEvents < 0) continue;

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
                if (bUseDelim) ReturnMessage.addstr("");
                ReturnMessage.addstr(ReceiveMessage.popstr());

                ReturnMessage.send(this->RouterSocket);
            }
        }
    }

    return 0;
}

void FRouter::Stop()
{
    this->bContinueRun = false;
}
    
void FRouter::Exit()
{
    // Do nothing for now (called when Run() ends)
}
