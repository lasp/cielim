//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of FCielimSceneViewExtension.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CielimSceneViewExtension.h"

#include "Utilities/Logging/CielimLoggingMacros.h"

bool FCielimSceneViewExtension::IsActiveThisFrame_Internal(const FSceneViewExtensionContext &Context) const
{
	// Always use this scene view extension
	return true;
}

void FCielimSceneViewExtension::SetupViewFamily(FSceneViewFamily &InViewFamily)
{
	// Do nothing for now
}

void FCielimSceneViewExtension::SetupView(FSceneViewFamily &InViewFamily, FSceneView &InView)
{
	InView.AntiAliasingMethod = AAM_FXAA;

	if (InView.ViewActor && !InView.ViewActor->GetClass()->GetName().Equals("PlayerController"))
	{
		UE_LOG(LogCielim, Warning, TEXT("View Actor: %s, Class: %s"), *InView.ViewActor->GetName(),
			   *InView.ViewActor->GetClass()->GetName());
	}
}
