//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FCielimSceneViewExtension class. This is used to extend the renderer and add
//          passes that run automatically for every view every frame.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "CoreMinimal.h"
#include "SceneViewExtension.h"

class CIELIM_API FCielimSceneViewExtension : public FSceneViewExtensionBase
{
public:
	explicit FCielimSceneViewExtension(const FAutoRegister &AutoRegister) : FSceneViewExtensionBase(AutoRegister) {}
	virtual ~FCielimSceneViewExtension() override {}

	// These functions are public but should never be called outside the engine

	virtual bool IsActiveThisFrame_Internal(const FSceneViewExtensionContext &Context) const override;

	virtual void SetupViewFamily(FSceneViewFamily &InViewFamily) override;
	virtual void SetupView(FSceneViewFamily &InViewFamily, FSceneView &InView) override;

	virtual void BeginRenderViewFamily(FSceneViewFamily &InViewFamily) override {}
	virtual void PreRenderView_RenderThread(FRDGBuilder &GraphBuilder, FSceneView &InView) override {}
	virtual void PreRenderViewFamily_RenderThread(FRDGBuilder &GraphBuilder, FSceneViewFamily &InViewFamily) override {}

	// virtual void PrePostProcessPass_RenderThread(FRDGBuilder &GraphBuilder, const FSceneView &View, const
	// FPostProcessingInputs &Inputs) override;
};
