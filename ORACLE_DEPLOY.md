# Бесплатный деплой на Oracle Cloud Always Free

Это по-настоящему бесплатно навсегда (не пробный период), но требует
выполнить набор команд в терминале при первой настройке — дальше сервер
работает сам, без вашего участия.

Общая схема: виртуальная машина в Oracle Cloud крутит вашего бота
круглосуточно, а бесплатный сервис **ngrok** даёт ему постоянный
HTTPS-адрес (без покупки домена — это единственная точка, где обычно
приходится платить, а ngrok это обходит).

---

## Шаг 1. Создать аккаунт Oracle Cloud

1. Зайдите на [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
   и зарегистрируйтесь. Попросят карту для подтверждения личности — в рамках
   Always Free с неё ничего не спишут, если не выходить за бесплатные лимиты.
2. Дождитесь письма о готовности аккаунта (иногда проверка занимает время).

## Шаг 2. Создать виртуальную машину

1. В консоли Oracle Cloud: **Menu → Compute → Instances → Create Instance**
2. **Image and shape** → **Edit** → выберите:
   - Image: **Ubuntu 22.04**
   - Shape: **Ampere → VM.Standard.A1.Flex** (это Always Free, возьмите 1 OCPU / 6 GB RAM)
3. В разделе **SSH keys** выберите **Generate a key pair for me** и скачайте
   приватный ключ (файл `.pem` или `.key`) — он даст вам доступ к серверу.
   Сохраните его в надёжном месте, второй раз скачать нельзя.
4. Нажмите **Create**. Через пару минут статус станет **Running** — на
   странице инстанса будет виден **Public IP Address**, он вам понадобится.

## Шаг 3. Открыть порт для ngrok-туннеля

Наружу открывать порт не нужно (ngrok сам создаёт исходящее соединение) —
достаточно того, что уже открыт SSH (порт 22), он включён по умолчанию.

## Шаг 4. Подключиться к серверу по SSH

**Mac/Linux** — в Терминале:
```bash
chmod 400 путь/к/скачанному-ключу.pem
ssh -i путь/к/скачанному-ключу.pem ubuntu@ВАШ_PUBLIC_IP
```

**Windows** — проще всего через PowerShell (та же команда, что выше) —
он поддерживает ssh «из коробки» в Windows 10/11.

При первом подключении спросит "Are you sure you want to continue
connecting?" — ответьте `yes`.

## Шаг 5. Установить всё необходимое на сервере

Выполняйте команды по одной, копируя целиком:

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git nano
```

## Шаг 6. Загрузить код бота на сервер

Проще всего — через ваш репозиторий на GitHub (из предыдущей инструкции):

```bash
git clone ССЫЛКА_НА_ВАШ_GITHUB_РЕПОЗИТОРИЙ fitbot
cd fitbot
```

Если репозитория ещё нет — можно закачать этот проект напрямую с вашего
компьютера командой (выполняется **не на сервере**, а в терминале на вашем
компьютере, из папки с проектом):
```bash
scp -i путь/к/ключу.pem -r ./fitbot ubuntu@ВАШ_PUBLIC_IP:~/fitbot
```

## Шаг 7. Установить зависимости и настроить .env

```bash
cd ~/fitbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

В открывшемся редакторе впишите реальные значения:
- `BOT_TOKEN` — токен от @BotFather
- `TRAINER_TG_ID` — ваш Telegram ID от @userinfobot
- `TRAINER_USERNAME` — ваш username без @
- `PUBLIC_URL` — впишем на следующем шаге, пока оставьте как есть
- `PORT=8080`

Сохранить в nano: `Ctrl+O`, затем `Enter`, выйти: `Ctrl+X`.

## Шаг 8. Настроить ngrok (постоянный бесплатный HTTPS-адрес)

1. На вашем компьютере (в браузере) зарегистрируйтесь на
   [ngrok.com](https://ngrok.com) — бесплатно
2. В личном кабинете: **Your Authtoken** — скопируйте токен
3. Там же: **Universal Gateway → Domains → + Create Domain** — получите
   бесплатный статический адрес вида `something-random.ngrok-free.app`
   (можно частично задать имя)
4. Вернитесь в SSH-сессию на сервере и установите ngrok:

```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok -y
ngrok config add-authtoken ВАШ_ТОКЕН_ИЗ_ЛИЧНОГО_КАБИНЕТА
```

5. Впишите этот адрес в `.env` на сервере:
```bash
nano ~/fitbot/.env
```
`PUBLIC_URL=https://ваш-адрес.ngrok-free.app` (без `/` в конце), сохраните.

## Шаг 9. Запустить бота и туннель так, чтобы они работали всегда

Это даст автозапуск при перезагрузке сервера и автоматический перезапуск,
если что-то упадёт.

```bash
sudo cp ~/fitbot/deploy/fitbot.service /etc/systemd/system/
sudo cp ~/fitbot/deploy/fitbot-tunnel.service /etc/systemd/system/
sudo nano /etc/systemd/system/fitbot-tunnel.service
```
В этом файле замените `YOUR-STATIC-DOMAIN.ngrok-free.app` на ваш реальный
адрес из шага 8.3, сохраните (`Ctrl+O`, `Enter`, `Ctrl+X`).

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable fitbot fitbot-tunnel
sudo systemctl start fitbot fitbot-tunnel
```

Проверить, что всё запустилось без ошибок:
```bash
sudo systemctl status fitbot
sudo systemctl status fitbot-tunnel
```
Должно быть написано `active (running)` зелёным. Если что-то красное —
смотрите подробности командой `journalctl -u fitbot -n 50` (или
`fitbot-tunnel` для туннеля) — там будет видна конкретная ошибка.

## Шаг 10. Настроить кнопку в @BotFather

`/mybots` → выберите бота → **Bot Settings → Menu Button → Configure Menu
Button** → вставьте `https://ваш-адрес.ngrok-free.app`

## Шаг 11. Проверка

Напишите боту `/start` — дальше как в основном README (пункт «Шаг 7. Проверка»).

---

## Что делать, если нужно обновить код бота в будущем

```bash
cd ~/fitbot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart fitbot
```

## На заметку про Always Free

Oracle иногда забирает («reclaim») инстансы Always Free, если они по их
метрикам выглядят «неиспользуемыми» подолгу — но бот, который постоянно
держит соединение с Telegram, обычно засчитывается как активность. Если
всё же случится — просто создаёте новый инстанс по этой же инструкции
(данные внутри сервера будут потеряны, поэтому раз в какое-то время имеет
смысл скачивать `fitbot.db` себе на компьютер командой с вашего компьютера:
`scp -i ключ.pem ubuntu@IP:~/fitbot/fitbot.db ./backup.db`).
