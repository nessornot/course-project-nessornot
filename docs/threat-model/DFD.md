# DFD — Data Flow Diagram

## Диаграмма (Mermaid)

```mermaid
flowchart LR
    U[User] -- "F1: Login (creds)" --> API[FastAPI App]
    API -- "F2: Auth Token (JWT)" --> U
    U -- "F3: API Request (JWT, payload)" --> API
    API -- "F6: API Response (data)" --> U

    subgraph Edge[Trust Boundary: Edge]
        style Edge stroke:#f00,stroke-width:2px,stroke-dasharray: 5 5
        API
    end

    subgraph Core[Trust Boundary: Core]
        style Core stroke:#f70,stroke-width:2px,stroke-dasharray: 5 5
        API -- "F4: SQL Query (owner_id, card_data)" --> DB[(Database)]
        DB -- "F5: SQL Result (card_data)" --> API
    end
```

## Список потоков

| ID | Откуда → Куда | Канал/Протокол | Данные/PII | Комментарий |
|----|---------------|-----------------|------------|-------------|
| F1 | User → API    | HTTPS           | `login`, `password` | Аутентификация пользователя |
| F2 | API → User    | HTTPS           | `JWT`      | Выдача токена сессии |
| F3 | User → API    | HTTPS           | `JWT`, `card_data` | Основные запросы к API (GET, POST, PATCH) |
| F4 | API → DB      | TCP/IP (TLS)    | SQL-запросы, PII | Чтение/запись данных карточек и пользователей |
| F5 | DB → API      | TCP/IP (TLS)    | Данные карточек | Получение данных из БД |
| F6 | API → User    | HTTPS           | Данные карточек | Ответ API с запрошенными данными |
| F7 | User → API    | HTTPS           | `JWT`, `column_id` | Перемещение карточки (`PATCH /move`) |
```
