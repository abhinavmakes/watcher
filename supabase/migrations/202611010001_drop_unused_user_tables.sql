-- user_preferences and user_keys were created for auth, per-user preferences and
-- bring-your-own-key chat. That scope was cut: the product is a public, read-only feed
-- and nothing reads or writes either table. Dropping them also removes the only place the
-- schema stored credentials, so the database no longer holds anything user-specific.
DROP TABLE IF EXISTS user_keys;
DROP TABLE IF EXISTS user_preferences;
