#include "KinematicsUtilities.h"

/* MRPtoDCM(q) returns the direction cosine matrix in terms of the 3x1 MRP vector q.
  @return UE::Math::TMatrix<double> direction cosine matrix
  @param FVector3d The MRP vector
 */
UE::Math::TMatrix<double> MRPtoDCM(FVector3d q) {
    auto rotationMatrix = UE::Math::TRotationMatrix<double>::Make(MRPtoQuaternion(q));
    return rotationMatrix;
}

/* MRPtoQuaternion(Q) translates the 3x1 MRP vector v into the Euler parameter (quaternion) vector.
  @return UE::Math::TQuat<double> quaternion vector
  @param FVector3d The MRP vector
 */
UE::Math::TQuat<double> MRPtoQuaternion(FVector3d v)
{
    double normSquared = v.SizeSquared();
    double ps = 1 + normSquared;
    return UE::Math::TQuat<double>(
                2 * v.X / ps,
                2 * v.Y / ps,
                2 * v.Z / ps,
                (1 - normSquared) / ps);
}

/**
 * @brief QuaterniontoMRP(q) translates the Euler parameter (quaternion) into a 3x1==x1 MRP vector.
 * 
 * @param q The Euler parameter (quaternion)
 * @return UE::Math::TVector<double> MRP vector 
 */
UE::Math::TVector<double> QuaterniontoMRP(FQuat q)
{
  double denom = 1 + q.W;
  return UE::Math::TVector<double>(q.X / denom, q.Y / denom, q.Z / denom);
}

/**
 * @brief RightQuat2LeftQuat(q) Maps right-handed quaternion q to left-handed quaternion.
 * 
 * @param q The right-handed quaternion
 * @return UE::Math::TQuat<double> The left-handed quaternion
 */
UE::Math::TQuat<double> RightQuat2LeftQuat(FQuat q) 
{
  return UE::Math::TQuat<double>(-q.X, q.Y, -q.Z, q.W);
}

/**
 * @brief Right2LeftVector(v) Maps right-handed vector v to left-handed vector.
 * 
 * @param v The right-handed vector
 * @return UE::Math::TVector<double> The left-handed vector
 */
UE::Math::TVector<double> Right2LeftVector(FVector3d v)
{
  return UE::Math::TVector<double>(v.X, -v.Y, v.Z);
}

