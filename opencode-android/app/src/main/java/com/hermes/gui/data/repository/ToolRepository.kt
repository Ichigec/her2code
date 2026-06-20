package com.hermes.gui.data.repository

import com.hermes.gui.data.remote.HermesApi
import com.hermes.gui.data.remote.dto.ToolsetDto
import com.hermes.gui.domain.model.Toolset
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ToolRepository @Inject constructor(
    private val api: HermesApi
) {

    suspend fun fetchToolsets(): Result<List<Toolset>> {
        return try {
            val response = api.getToolsets()
            if (response.isSuccessful) {
                val dtos = response.body()?.data ?: emptyList()
                Result.success(dtos.map { it.toDomain() })
            } else {
                Result.failure(Exception("Failed to fetch toolsets: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun ToolsetDto.toDomain(): Toolset {
        return Toolset(
            name = name,
            label = label ?: name,
            description = description ?: "",
            enabled = enabled,
            configured = configured,
            tools = tools
        )
    }
}
