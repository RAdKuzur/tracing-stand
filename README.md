Для начала работы написать в консоли:
1. cp .env.example .env
2. docker compose up --build -d
3. Перейти на http://localhost:8080/ , для появления трейса перейти на http://localhost:8081/


Для проверки работоспособности:
1. python scripts/verify.py

Для проведения тестирования написать:
1. docker compose up --build tests-collector          
2. docker compose up --build tests-ui 
