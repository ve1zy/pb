# SQLite: Практическое руководство

## Введение
SQLite — встраиваемая реляционная база данных.
Не требует отдельного серверного процесса. Все данные в одном файле.
Идеальна для мобильных приложений, десктопных программ, прототипирования.

## Создание таблицы
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

## Операции CRUD
INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com');
SELECT * FROM users WHERE name LIKE '%Alice%';
UPDATE users SET email = 'new@example.com' WHERE id = 1;
DELETE FROM users WHERE id = 1;

## Транзакции
BEGIN TRANSACTION;
INSERT INTO accounts (balance) VALUES (100);
INSERT INTO transfers (from_id, to_id, amount) VALUES (1, 2, 50);
COMMIT;

## Индексы
CREATE INDEX idx_users_email ON users(email);
Индексы ускоряют поиск, но замедляют запись.

## Python интеграция
import sqlite3
conn = sqlite3.connect('mydb.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM users')
rows = cursor.fetchall()
conn.close()

## Оптимизация
WAL режим: PRAGMA journal_mode=WAL;
Vacuum: сжатие базы данных.
Backup API для безопасного резервного копирования.
