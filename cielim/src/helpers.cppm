// Copyright (c) 2026 Laboratory for Atmospheric and Space Physics
// SPDX-License-Identifier: GPL-3.0+

/* Purpose: Provides standard helper functions. */

module;

#include <concepts>
#include <cstddef>
#include <format>
#include <functional>
#include <system_error>

export module cielim.helpers;

import cielim.error;
import cielim.result;

// Export to project-level namespace because this is generic enough
export namespace cielim
{

// A container that can be measured and randomly accessed by index, e.g., std::vector or std::array
template <typename Container>
concept IndexableContainer = requires(const Container& container, const std::size_t index) {
    typename Container::value_type;
    { container.size() } -> std::convertible_to<std::size_t>;
    { container[index] } -> std::convertible_to<const typename Container::value_type&>;
};

/**
 * @brief Gets an immutable reference to the element in a container at an index.
 * @param container The container to access.
 * @param index The index of the element from which the container should retrieve.
 * @return A reference to the element at the index on success, error code if index is out of bounds.
 */
template <IndexableContainer Container>
auto try_at_ref(const Container& container, const std::size_t index)
    -> Result<std::reference_wrapper<const typename Container::value_type>>
{
    if (index >= container.size())
    {
        error::DetailedError error = {
            .errc = std::make_error_code(std::errc::argument_out_of_domain),
            .detail = std::format("index {} is out of bounds for size {}", index, container.size()),
        };

        return Err(error);
    }

    return std::cref(container[index]);
}

/**
 * @brief Gets a copy of the element in a container at an index.
 * @param container The container to access.
 * @param index The index of the element from which the container should retrieve.
 * @return A copy of the element at the index on success, error code if index is out of bounds.
 */
template <IndexableContainer Container>
auto try_at(const Container& container, const std::size_t index) -> Result<typename Container::value_type>
{
    const auto ref_result = try_at_ref(container, index);

    if (!ref_result.has_value())
        return ref_result.propagate();

    return ref_result.value().get();
}

} // namespace cielim
