//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the UCameraViewCaptureComponent2D class. This is a subclass of the USceneCaptureComponent2D
//          class used to capture the scene into a 2D render target. This subclass extends the SCC2D interface
//          to better work with CameraModel.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"

#include "Components/SceneCaptureComponent2D.h"

#include "CameraViewCaptureComponent2D.generated.h"

UCLASS()
class CIELIM_API UCameraViewCaptureComponent2D : public USceneCaptureComponent2D
{
	GENERATED_BODY()

public:
	virtual const AActor *GetViewOwner() const override;
};
