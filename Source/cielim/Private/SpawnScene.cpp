// MIT LicenseCopyright (c) 2023 Laboratory for Atmospheric and Space PhysicsPermission is hereby granted, free of charge, to any person obtaining a copyof this software and associated documentation files (the "Software"), to dealin the Software without restriction, including without limitation the rightsto use, copy, modify, merge, publish, distribute, sublicense, and/or sellcopies of the Software, and to permit persons to whom the Software isfurnished to do so, subject to the following conditions:The above copyright notice and this permission notice shall be included in allcopies or substantial portions of the Software.THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS ORIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THEAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHERLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THESOFTWARE.


#include "SpawnScene.h"
#include "CaptureManager.h"
#include "CielimLoggingMacros.h"

// Sets default values
ASpawnScene::ASpawnScene()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

}

// Called when the game starts or when spawned
void ASpawnScene::BeginPlay()
{
	//TODO: Spawn spacecraft actor and a point source light

	UE_LOG(LogCielim, Warning, TEXT("Spawning Scene"));
	//Init spacecraft and light positions
	FVector3d SpacecraftPosition {0,0,height};
	FVector3d PointLightPosition {radius,0,height};
	
	//Init spacecraft and light rotations
	FRotator SpacecraftRotation = FRotator::ZeroRotator;
	FRotator PointLightRotation = FRotator::ZeroRotator;

	//Spawn spacecraft actor
	Spacecraft = GetWorld()->SpawnActor<ASpacecraft>(BpSpacecraft, SpacecraftPosition, SpacecraftRotation);
	UE_LOG(LogCielim, Warning, TEXT("Spacecraft Spawned"));

	//Spawn light actor
	PointLight = GetWorld()->SpawnActor<APointLightActor>(BpPointLight, PointLightPosition, PointLightRotation);
	UE_LOG(LogCielim, Warning, TEXT("PointLight Spawned"));
	UE_LOG(LogCielim, Warning, TEXT("Scene Spawned"));
	
	Super::BeginPlay();
	
}

// Called every frame
void ASpawnScene::Tick(float DeltaTime)
{
	//If the light source has changed directions less than twice... in the horizontal direction
	if(alpha_flag_changes < 2)
	{
		//if the light source is outside the right bound
		if(alpha > PI / 4)
		{
			clockwise_flag = false;
			alpha_flag_changes++;
		}
		//if the light source is outside the left bound
		else if(alpha < -1 * PI / 4)
		{
			clockwise_flag = true;
			alpha_flag_changes++;
		}
		//if the light source is going clockwise
		if(clockwise_flag)
		{
			alpha += 2 * PI / 4 / 200;
			UpdateHorizontalPointLight(alpha, radius, height);
		}
		//if the light source is going counter-clockwise
		else
		{
			alpha -= 2 * PI / 4 / 200;
			UpdateHorizontalPointLight(alpha, radius, height);
		}
	}
	//If the light source has changed directions less than twice... in the vertical direction
	else if(beta_flag_changes < 2)
	{
		ResetPointLight(radius, height);
		//if the light source is outside the upper(?) bound
		if(beta > PI / 4)
		{
			clockwise_flag = false;
			beta_flag_changes++;
		}
		//if the light source is outside the lower(?) bound
		else if(beta < -1 * PI / 4)
		{
			clockwise_flag = true;
			beta_flag_changes++;
		}
		//if the light source is going clockwise
		if(clockwise_flag)
		{
			beta += 2 * PI / 4 / 200;
			UpdateVerticalPointLight(beta, radius, height);
		}
		//if the light source is going counter-clockwise
		else
		{
			beta -= 2 * PI / 4 / 200;
			UpdateVerticalPointLight(beta, radius, height);
		}
	}

	//if the light source has gone both ways in the vertical and horizontal directions, reset all the parameters and start over
	else
	{
		alpha_flag_changes = 0;
		beta_flag_changes = 0;
		alpha = -1 * PI / 4;
		beta = -1 * PI / 4;
		ResetPointLight(radius, height);
	}
	
	Super::Tick(DeltaTime);
}

void ASpawnScene::UpdateHorizontalPointLight(float a, float r, float h)
{
	this->PointLight->UpdateHorizontalPath(a, r, h);
}

void ASpawnScene::UpdateVerticalPointLight(float b, float r, float h)
{
	this->PointLight->UpdateVerticalPath(b, r, h);
}

void ASpawnScene::ResetPointLight(float r, float h)
{
	this->PointLight->ResetPosition(r, h);
}
