package com.hermes.gui.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class TranscriptionResponse(
    val transcript: String
)

@JsonClass(generateAdapter = true)
data class SpeakRequest(
    val text: String
)

@JsonClass(generateAdapter = true)
data class SpeakResponse(
    @Json(name = "data_url") val dataUrl: String
)

@JsonClass(generateAdapter = true)
data class TranscribeRequest(
    val audio: String  // "data:audio/ogg;base64,..."
)
