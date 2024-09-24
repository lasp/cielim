#pragma once

#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"
#include "CielimLoggingMacros.h"
#include "Misc/SingleThreadRunnable.h"

class FThreadBase : public FRunnable, FSingleThreadRunnable
{
public:

	/**
	 * @param threadTickRate The amount of time to wait between loops.
	 * @param threadDescription The thread description text (for debugging).
	 */
	FThreadBase(const FTimespan& threadTickRate, const TCHAR* threadDescription)
		: Stopping(false)
		, ThreadTickRate(threadTickRate)
	{
		Paused.AtomicSet(false);
		// Thread = FRunnableThread::Create(this, 
		// 								threadDescription, 
		// 								128 * 1024,  //allocated memory
		// 								TPri_AboveNormal, 
		// 								FPlatformAffinity::GetPoolThreadMask());
	}

	/** Virtual destructor. */
	virtual ~FThreadBase()
	{
		if (Thread != nullptr)
		{
			Thread->Kill(true);
			delete Thread;
		}
	}

public:
	
	//Run this if you know your thread is waiting / has nothing to do for a while
	// Avoid using unnecessary OS resources!
	void Wait(float Seconds)
	{
		UE_LOG(LogCielim, Warning, TEXT("FThreadBase::Wait"));
		FPlatformProcess::Sleep(Seconds);
	}
	
	//FRunnable interface
	/**
	 * Returns a pointer to the single threaded interface when mulithreading is disabled.
	 */
	virtual FSingleThreadRunnable* GetSingleThreadInterface() override
	{
		return this;
	}

	// FSingleThreadRunnable interface
	virtual void Tick() override
	{
		CustomTick();
	}
	
	//To be Subclassed
	virtual void CustomTick() {}
	
public:
	// FRunnable interface
	virtual bool Init() override
	{
		return true;
	}

	virtual uint32 Run() override
	{
		HasStopped.AtomicSet(false);
		
		while (!Stopping)
		{
			if(Paused)
			{
				if(!IsVerifiedSuspended)
				{
					IsVerifiedSuspended.AtomicSet(true);
				}
				// No custom Ticks Will Occur!
				//! Ready to resume on a moments notice though!
				Wait(ThreadTickRate.GetTotalSeconds());
				continue;
			}
			CustomTick();
		}
		HasStopped.AtomicSet(true);
		return 0;
	}

	virtual void Stop() override
	{
		SetPaused(true);
		Stopping = true;
	}
	
	void SetPaused(bool MakePaused)
	{
		Paused.AtomicSet(MakePaused);
		if(!MakePaused)
		{
			IsVerifiedSuspended.AtomicSet(false);
		}
		//! verified paused has to come after custom Tick completes
	}
    
	bool ThreadIsPaused()
	{
		return Paused;
	}
	
	//No more custom Ticks will occur!
	bool ThreadIsVerifiedSuspended()
	{
		return IsVerifiedSuspended;
	}
    
	bool ThreadHasStopped()
	{
		return HasStopped;
	}
	
protected:
	
	FThreadSafeBool Paused;
	FThreadSafeBool IsVerifiedSuspended;
	FThreadSafeBool HasStopped;
	
	/** Holds a flag indicating that the thread is stopping. */
	bool Stopping;

	/** Holds the thread object. */
	FRunnableThread* Thread;

	/** Holds the amount of time to wait */
	FTimespan ThreadTickRate;
};
