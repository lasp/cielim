//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Defines the FCielimModule class which is used to implement the Cielim module that is
//          recognized by Unreal Engine.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#pragma once

#include "Modules/ModuleManager.h"

class FCielimModule final : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
