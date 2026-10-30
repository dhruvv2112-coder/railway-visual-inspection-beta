# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class org.rvi.inspect.** { *** Companion; }
-keepclasseswithmembers class org.rvi.inspect.** { kotlinx.serialization.KSerializer serializer(...); }
