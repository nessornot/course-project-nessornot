# Hardening Summary

## 1. Dockerfile
- Используется фиксированная версия `python:3.12-slim-bookworm`
- Процесс запускается от непривилегированного пользователя `app`
- Используется multi-stage build для уменьшения размера образа

## 2. IaC
  - `runAsNonRoot: true` - запрет запуска от root
  - `readOnlyRootFilesystem: true` - защита файловой системы контейнера
  - `capabilities.drop: ["ALL"]` - сброс всех лишних привилегий linux
  - Установлены `requests` и `limits` для CPU и RAM для защиты от DoS
