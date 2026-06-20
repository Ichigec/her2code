package com.hermes.gui.di

import android.content.Context
import androidx.room.Room
import com.hermes.gui.data.local.AppDatabase
import com.hermes.gui.data.local.dao.ConversationDao
import com.hermes.gui.data.local.dao.MessageDao
import com.hermes.gui.data.remote.HealthCheckManager
import com.hermes.gui.data.remote.HermesApi
import com.hermes.gui.data.remote.SseClient
import com.hermes.gui.data.remote.interceptor.AuthInterceptor
import com.hermes.gui.data.repository.VoiceRepository
import com.hermes.gui.data.settings.SettingsDataStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideSettingsDataStore(
        @ApplicationContext context: Context
    ): SettingsDataStore {
        return SettingsDataStore(context)
    }

    @Provides
    @Singleton
    fun provideHealthCheckManager(
        settingsDataStore: SettingsDataStore
    ): HealthCheckManager {
        return HealthCheckManager(settingsDataStore)
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(
                HttpLoggingInterceptor().apply {
                    level = HttpLoggingInterceptor.Level.HEADERS
                }
            )
            .retryOnConnectionFailure(true)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient,
        settingsDataStore: SettingsDataStore
    ): Retrofit {
        return Retrofit.Builder()
            .baseUrl("http://localhost:8642/") // Fallback, overridden at request time
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideHermesApi(retrofit: Retrofit): HermesApi {
        return retrofit.create(HermesApi::class.java)
    }

    @Provides
    @Singleton
    fun provideSseClient(): SseClient {
        return SseClient()
    }

    @Provides
    @Singleton
    fun provideAppDatabase(
        @ApplicationContext context: Context
    ): AppDatabase {
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "hermes_gui_db"
        )
            .fallbackToDestructiveMigration()
            .build()
    }

    @Provides
    @Singleton
    fun provideConversationDao(database: AppDatabase): ConversationDao {
        return database.conversationDao()
    }

    @Provides
    @Singleton
    fun provideMessageDao(database: AppDatabase): MessageDao {
        return database.messageDao()
    }

    @Provides
    @Singleton
    fun provideVoiceRepository(): VoiceRepository {
        return VoiceRepository()
    }
}
