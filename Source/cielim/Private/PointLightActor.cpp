// MIT LicenseCopyright (c) 2023 Laboratory for Atmospheric and Space PhysicsPermission is hereby granted, free of charge, to any person obtaining a copyof this software and associated documentation files (the "Software"), to dealin the Software without restriction, including without limitation the rightsto use, copy, modify, merge, publish, distribute, sublicense, and/or sellcopies of the Software, and to permit persons to whom the Software isfurnished to do so, subject to the following conditions:The above copyright notice and this permission notice shall be included in allcopies or substantial portions of the Software.THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS ORIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THEAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHERLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THESOFTWARE.


#include "PointLightActor.h"
#include "SpawnScene.h"


// Sets default values
APointLightActor::APointLightActor()
{

}

// Called when the game starts or when spawned
void APointLightActor::BeginPlay()
{
	Super::BeginPlay();
}

// Called every frame
void APointLightActor::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

void APointLightActor::UpdateHorizontalPath(float angle, float radius, float height)
{
	FVector3d new_position {radius * cos(angle), radius * sin(angle), height};
	SetActorLocation(new_position);
}

void APointLightActor::UpdateVerticalPath(float angle, float radius, float height)
{
	FVector3d new_position {radius * cos(angle), 0, radius * sin(angle) + height};
	SetActorLocation(new_position);
}

void APointLightActor::ResetPosition(float radius, float height)
{
	FVector3d new_position {radius,0,height};
	SetActorLocation(new_position);
}