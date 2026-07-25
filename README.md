# Cantina — Sistema de Pedidos

Sistema web para organizar pedidos de uma cantina durante eventos.

Conecta três telas em tempo real:

- **Atendente** — registra novos pedidos
- **Cozinha** — visualiza e prepara os pedidos
- **Painel** — mostra aos clientes quais pedidos estão prontos para retirada

Todos os dispositivos se comunicam instantaneamente via WebSocket. Não é necessário atualizar a página.

---

## Funcionalidades

- Pedidos numerados de **1 a 300**, cada número usado apenas uma vez
- Fluxo completo: `AGUARDANDO → PREPARO → PRONTO → ENTREGUE`
- Confirmação visual ao enviar pedido
- Alerta sonoro no painel quando um pedido fica pronto
- Dados persistidos em SQLite (sobrevive a reinicializações)
- Funciona **sem internet** — apenas rede local

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado

Não é necessário instalar Python, pip ou qualquer dependência manualmente.

---

## Como utilizar

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU-LOGIN/cantina.git
cd cantina
```

### 2. Subir o sistema

```bash
docker compose up -d --build
```

### 3. Acessar as telas

Descubra o IP da máquina que está rodando o servidor:

```bash
# Linux
hostname -I

# Windows
ipconfig
```

Acesse nos dispositivos:

| Finalidade | URL |
|---|---|
| Atendente | `http://localhost:8000` |
| Cozinha | `http://localhost:8000/cozinha` |
| Painel (TV/projetor) | `http://localhost:8000/painel` |

> Todos os dispositivos devem estar na **mesma rede WiFi**.

### 4. Parar o sistema

```bash
docker compose stop
```

Os dados são preservados.

### 5. Reiniciar

```bash
docker compose start
```

### 6. Limpar tudo (apagar pedidos)

```bash
docker compose down -v
```

---

## Fluxo de uso

```
1. Cliente faz pedido
        ↓
2. Atendente registra na tela
        ↓
3. Cozinha recebe automaticamente
        ↓
4. Cozinha clica "Iniciar preparo"
        ↓
5. Cozinha clica "Pronto"
        ↓
6. Número aparece no painel + som
        ↓
7. Cliente vê seu número e vai ao balcão
        ↓
8. Cozinha entrega e clica "Entregue"
```

---

## Estrutura do projeto

```
cantina/
├── app.py                 # Backend (FastAPI + WebSocket + SQLite)
├── requirements.txt       # Dependências Python
├── Dockerfile             # Configuração da imagem Docker
├── docker-compose.yml     # Orquestração do container
├── templates/
│   ├── atendente.html     # Tela do atendente
│   ├── cozinha.html       # Tela da cozinha
│   └── painel.html        # Painel público
└── static/
    ├── style.css          # Estilos
    ├── bootstrap.min.css  # Bootstrap (local)
    ├── bootstrap.bundle.min.js
    └── sons/
        └── pronto.mp3     # Som de alerta
```
