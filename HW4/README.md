# Запуск всех сервисов
./infra/starting_services.sh ЛИБО ЖЕ docker-compose up -d --build

# Создание топиков 
./infra/create_topics.sh

# Применение миграций БД
./infra/apply_migrations.sh

# Наполнение тестовыми данными
docker-compose exec postgres psql -U postgres -d advertisement_db -c "INSERT INTO users (id, login, password, email, is_verified_seller, created_at, updated_at) VALUES (1, 'seller', 'pass', 's@test.com', true, NOW(), NOW()) ON CONFLICT (id) DO NOTHING;"
docker-compose exec postgres psql -U postgres -d advertisement_db -c "INSERT INTO advertisements (id, seller_id, name, description, category, images_qty, created_at, updated_at) VALUES (10, 1, 'Test Item', 'Desc', 1, 5, NOW(), NOW()) ON CONFLICT (id) DO NOTHING;"

# Отправка объявления на модерацию
curl -X POST "http://localhost:8000/moderation/async_predict" -H "Content-Type: application/json" -d '{"item_id": 10}'

# Проверка результата (task_id=1)
curl "http://localhost:8000/moderation/moderation_result/1"

# Просмотр логов воркера
docker-compose logs -f worker