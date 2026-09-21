// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Loads mesh data from glTF format. */

module;

#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <utility>
#include <vector>

#include <fastgltf/core.hpp>
#include <fastgltf/tools.hpp>

export module cielim.mesh:loader;

import cielim.error;
import cielim.result;
// import cielim.utils; This causes C1116 with MSVC 14.51, can be re-introduced when compiler bug is fixed
import :elements;

export namespace cielim::mesh
{

class Loader
{
public:
    Loader() = default;

    // Delete copy constructors

    Loader(const Loader&) = delete;
    auto operator=(const Loader&) -> Loader& = delete;

    // Use default move constructors

    Loader(Loader&&) = default;
    auto operator=(Loader&&) -> Loader& = default;

    /**
     * @brief Loads mesh data from a glTF binary file on disk.
     * @param path The path to the .glb file.
     * @return Mesh data struct on success, error code on failure.
     */
    static auto load_mesh(const std::filesystem::path& path) -> Result<MeshData>
    {
        const std::string file_name = path.filename().string();

        fastgltf::Parser parser;

        auto data_result = fastgltf::GltfDataBuffer::FromPath(path);

        if (data_result.error() != fastgltf::Error::None)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MeshLoadError),
                    .detail = "'" + file_name + "': "
                            + error::sanitize_fragment(std::string(fastgltf::getErrorMessage(data_result.error()))),
                }
            );
        }

        auto asset_result
            = parser.loadGltf(data_result.get(), path.parent_path(), fastgltf::Options::LoadExternalBuffers);

        if (asset_result.error() != fastgltf::Error::None)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MeshLoadError),
                    .detail = "'" + file_name + "': "
                            + error::sanitize_fragment(std::string(fastgltf::getErrorMessage(asset_result.error()))),
                }
            );
        }

        fastgltf::Asset& gltf_asset = asset_result.get();

        MeshData mesh_data;

        // We are assuming that there is only a single object in the file
        const auto& primitive = gltf_asset.meshes[0].primitives[0];

        // Populate mesh data vertex positions

        const fastgltf::Attribute* position_iterator = primitive.findAttribute("POSITION");

        if (position_iterator == primitive.attributes.end())
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MalformedMesh),
                    .detail = "'" + file_name + "': missing vertex positions",
                }
            );
        }

        const fastgltf::Accessor& position_accessor = gltf_asset.accessors[position_iterator->accessorIndex];

        mesh_data.vertices.resize(position_accessor.count);

        fastgltf::iterateAccessorWithIndex<fastgltf::math::fvec3>(
            gltf_asset,
            position_accessor,
            [&](const fastgltf::math::fvec3 v, const size_t slot) -> void
            { mesh_data.vertices[slot].position = {v.x(), v.y(), v.z()}; }
        );

        // Populate mesh data vertex normals

        const fastgltf::Attribute* normal_iterator = primitive.findAttribute("NORMAL");

        if (normal_iterator == primitive.attributes.end())
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MalformedMesh),
                    .detail = "'" + file_name + "': missing vertex normals",
                }
            );
        }

        const auto& normal_accessor = gltf_asset.accessors[normal_iterator->accessorIndex];

        if (normal_accessor.count != position_accessor.count)
        {
            return Err(
                error::DetailedError{
                    .errc = make_error_code(error::MeshError::MalformedMesh),
                    .detail = "'" + file_name + "': vertex position and normal counts do not match",
                }
            );
        }

        fastgltf::iterateAccessorWithIndex<fastgltf::math::fvec3>(
            gltf_asset,
            normal_accessor,
            [&](const fastgltf::math::fvec3 n, const size_t slot) -> void
            { mesh_data.vertices[slot].normal = {n.x(), n.y(), n.z()}; }
        );

        // Populate mesh data indices

        const fastgltf::Accessor& index_accessor = gltf_asset.accessors[primitive.indicesAccessor.value()];

        mesh_data.indices.resize(index_accessor.count);

        fastgltf::iterateAccessorWithIndex<uint32_t>(
            gltf_asset,
            index_accessor,
            [&](const uint32_t index, const size_t slot) -> void { mesh_data.indices[slot] = index; }
        );

        /*utils::log::info(
            "Loaded mesh '{}' ({} vertices, {} indices)", file_name, mesh_data.vertices.size(), mesh_data.indices.size()
        );*/

        return std::move(mesh_data);
    }
};

} // namespace cielim::mesh
