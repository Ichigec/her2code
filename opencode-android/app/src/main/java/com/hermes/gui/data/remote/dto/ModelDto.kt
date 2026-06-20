package com.hermes.gui.data.remote.dto

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ModelsResponse(
    val `object`: String = "list",
    val data: List<ModelDto> = emptyList()
)

@JsonClass(generateAdapter = true)
data class ModelDto(
    val id: String,
    val `object`: String = "model",
    val created: Long? = null,
    val ownedBy: String? = null
)
