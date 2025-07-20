//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the definition of the FCielimModule class and the Cielim module.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "cielim.h"

void FCielimModule::StartupModule()
{
	// Register shader directory
	AddShaderSourceDirectoryMapping(TEXT("/CielimShaders"),
									FPaths::Combine(FPaths::ProjectDir(), TEXT("Source/cielim/Shaders")));
}

void FCielimModule::ShutdownModule()
{
	// Do nothing for now
}

IMPLEMENT_PRIMARY_GAME_MODULE(FCielimModule, cielim, "cielim");
