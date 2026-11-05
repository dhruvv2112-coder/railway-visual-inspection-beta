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
    val tpcInformedAt: Long? = null,
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

@Database(entities = [PatrolEntity::class, FindingEntity::class, OheSessionEntity::class, OheCaptureEntity::class, OheNoteEntity::class],
    version = 5, exportSchema = false)
abstract class RviDatabase : RoomDatabase() {
    abstract fun patrols(): PatrolDao
    abstract fun findings(): FindingDao
    abstract fun ohe(): OheDao

    companion object {
        fun build(context: Context) = Room.databaseBuilder(context, RviDatabase::class.java, "rvi.db")
            .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5).build()

        /** v2: OHE danger record (TPC informed) for the combined track + OHE foot patrol. */
        val MIGRATION_1_2 = object : androidx.room.migration.Migration(1, 2) {
            override fun migrate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE finding ADD COLUMN tpcInformedAt INTEGER")
            }
        }

        /** v5: phone roll at capture, for the mast lean check. */
        val MIGRATION_4_5 = object : androidx.room.migration.Migration(4, 5) {
            override fun migrate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE ohe_capture ADD COLUMN rollDeg REAL")
            }
        }

        /** v4: what the detector saw on each photo, and how many parts it could judge (shown after each photo). */
        val MIGRATION_3_4 = object : androidx.room.migration.Migration(3, 4) {
            override fun migrate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE ohe_capture ADD COLUMN seen TEXT NOT NULL DEFAULT ''")
                db.execSQL("ALTER TABLE ohe_capture ADD COLUMN assessed INTEGER NOT NULL DEFAULT 0")
            }
        }

        /** v3: OHE Visual AI Patrol capture flow (HLD v1.0) – sessions, photos, isolated notes. */
        val MIGRATION_2_3 = object : androidx.room.migration.Migration(2, 3) {
            override fun migrate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                db.execSQL("CREATE TABLE IF NOT EXISTS `ohe_session` (`id` TEXT NOT NULL, `territory` TEXT NOT NULL, `inspectorId` TEXT NOT NULL, " +
                    "`role` TEXT NOT NULL, `startedAt` INTEGER NOT NULL, `endedAt` INTEGER, `remoteId` TEXT, `reportId` TEXT, `summaryJson` TEXT, PRIMARY KEY(`id`))")
                db.execSQL("CREATE TABLE IF NOT EXISTS `ohe_capture` (`id` TEXT NOT NULL, `sessionId` TEXT NOT NULL, `path` TEXT NOT NULL, " +
                    "`sha256` TEXT NOT NULL, `capturedAt` INTEGER NOT NULL, `lat` REAL, `lon` REAL, `accuracyM` REAL, `localQualityOk` INTEGER NOT NULL, " +
                    "`localReasons` TEXT NOT NULL, `uploaded` INTEGER NOT NULL, `imageState` TEXT, `prompt` TEXT, `findings` INTEGER NOT NULL, " +
                    "`alert` INTEGER NOT NULL, PRIMARY KEY(`id`))")
                db.execSQL("CREATE TABLE IF NOT EXISTS `ohe_note` (`id` TEXT NOT NULL, `sessionId` TEXT NOT NULL, `text` TEXT NOT NULL, " +
                    "`createdAt` INTEGER NOT NULL, `uploaded` INTEGER NOT NULL, PRIMARY KEY(`id`))")
            }
        }
    }
}
