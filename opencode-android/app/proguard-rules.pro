# Add project specific ProGuard rules here.
# Hermes GUI ProGuard rules

# Retrofit
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.hermes.gui.data.remote.dto.** { *; }
-keepclassmembers class com.hermes.gui.data.remote.dto.** { *; }

# Moshi
-keep class com.squareup.moshi.** { *; }
-keep @com.squareup.moshi.JsonQualifier interface *

# Room
-keep class com.hermes.gui.data.local.entity.** { *; }
-keepclassmembers class com.hermes.gui.data.local.entity.** { *; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}
