package org.rvi.inspect.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.Update
import kotlinx.coroutines.flow.Flow
import java.util.UUID

/** Offline-first store: everything is written locally first and synced by WorkManager. */
@Entity(tableName = "patrol")
data class PatrolEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val patrolType: String,
    val inspectorId: String,
    val role: String,
    val beatFromKm: String,
    val beatToKm: String,
    val line: String,
    val kitCheckOk: Boolean,
    val startedAt: Long = System.currentTimeMillis(),
    val endedAt: Long? = null,
    val remoteId: String? = null,
)

@Entity(tableName = "finding")
data class FindingEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val patrolId: String,
    val classId: String,
    val kmReference: String,
    val line: String,
    val railSide: String,
    val lat: Double?,
    val lon: Double?,
    val gnssAccuracyM: Float?,
    val note: String,
    val noteLanguage: String,
    val actionTaken: String,
    val lineProtectedAt: Long?,
    val smInformedAt: Long?,
    val imagePath: String?,
    val qualityPassed: Boolean,
    val qualityReasons: String,
    val createdAt: Long = System.currentTimeMillis(),
    val synced: Boolean = false,
    val remoteId: String? = null,
)

@Dao
interface PatrolDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(p: PatrolEntity)
    @Update suspend fun update(p: PatrolEntity)
    @Query("SELECT * FROM patrol WHERE endedAt IS NULL ORDER BY startedAt DESC LIMIT 1") fun active(): Flow<PatrolEntity?>
    @Query("SELECT * FROM patrol WHERE id = :id") suspend fun get(id: String): PatrolEntity?
}

@Dao
interface FindingDao {
    @Insert suspend fun insert(f: FindingEntity)
    @Update suspend fun update(f: FindingEntity)
    @Query("SELECT * FROM finding WHERE patrolId = :patrolId ORDER BY createdAt") fun forPatrol(patrolId: String): Flow<List<FindingEntity>>
    @Query("SELECT * FROM finding WHERE synced = 0") suspend fun unsynced(): List<FindingEntity>
    @Query("SELECT COUNT(*) FROM finding WHERE synced = 0") fun pendingCount(): Flow<Int>
    @Query("SELECT * FROM finding ORDER BY createdAt DESC LIMIT 200") fun recent(): Flow<List<FindingEntity>>
}

@Database(entities = [PatrolEntity::class, FindingEntity::class], version = 1, exportSchema = false)
abstract class RviDatabase : RoomDatabase() {
    abstract fun patrols(): PatrolDao
    abstract fun findings(): FindingDao

    companion object {
        fun build(context: Context) = Room.databaseBuilder(context, RviDatabase::class.java, "rvi.db").build()
    }
}
