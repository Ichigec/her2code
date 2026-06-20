package com.hermes.gui.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.hermes.gui.data.local.dao.ConversationDao
import com.hermes.gui.data.local.dao.MessageDao
import com.hermes.gui.data.local.entity.ConversationEntity
import com.hermes.gui.data.local.entity.MessageEntity

@Database(
    entities = [
        ConversationEntity::class,
        MessageEntity::class
    ],
    version = 2,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDao
    abstract fun messageDao(): MessageDao
}
