#include "KinematicsUtilities.h"

/* MRPtoDCM(q) returns the direction cosine matrix in terms of the 3x1 MRP vector q.
  @return UE::Math::TMatrix<double> direction cosine matrix
  @param FVector3d The MRP vector
 */
UE::Math::TMatrix<double> MRPtoDCM(FVector3d q) {
    const auto RotationMatrix = UE::Math::TRotationMatrix<double>::Make(MRPtoQuaternion(q));
    return RotationMatrix;
}

/* MRPtoQuaternion(Q) translates the 3x1 MRP vector v into the Euler parameter (quaternion) vector.
  @return UE::Math::TQuat<double> quaternion vector
  @param FVector3d The MRP vector
 */
UE::Math::TQuat<double> MRPtoQuaternion(const FVector3d& v)
{
    const double NormSquared = v.SizeSquared();
    const double Ps = 1 + NormSquared;
    return UE::Math::TQuat(
                2 * v.X / Ps,
                2 * v.Y / Ps,
                2 * v.Z / Ps,
                (1 - NormSquared) / Ps);
}

/**
 * @brief QuaterniontoMRP(q) translates the Euler parameter (quaternion) into a 3x1==x1 MRP vector.
 * 
 * @param q The Euler parameter (quaternion)
 * @return UE::Math::TVector<double> MRP vector 
 */
UE::Math::TVector<double> QuaterniontoMRP(const FQuat& q)
{
  const double Denom = 1 + q.W;
  return UE::Math::TVector<double>(q.X / Denom, q.Y / Denom, q.Z / Denom);
}

/**
 * @brief RightQuat2LeftQuat(q) Maps right-handed quaternion q to left-handed quaternion.
 * 
 * @param q The right-handed quaternion
 * @return UE::Math::TQuat<double> The left-handed quaternion
 */
UE::Math::TQuat<double> RightQuat2LeftQuat(const FQuat& q) 
{
  return UE::Math::TQuat<double>(-q.X, q.Y, -q.Z, q.W);
}

/**
 * @brief Right2LeftVector(v) Maps right-handed vector v to left-handed vector.
 * 
 * @param v The right-handed vector
 * @return UE::Math::TVector<double> The left-handed vector
 */
UE::Math::TVector<double> Right2LeftVector(const FVector3d& v)
{
  return UE::Math::TVector<double>(v.X, -v.Y, v.Z);
}

