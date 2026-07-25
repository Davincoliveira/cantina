from datetime import datetime
import json
import sqlite3
import os
import threading

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI(title="Cantina")


app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# ============================================================
# PRODUTOS
# ============================================================

PRODUTOS = [
    "Hambúrguer de Carne",
    "Hambúrguer de Frango",
    "Batata Frita (150g)",
    "Refrigerante em Lata",
    "Suco à Parte",
    "Combo de Carne",
    "Combo de Frango"
]

COMBOS = ["Combo de Carne", "Combo de Frango"]


# ============================================================
# BANCO DE DADOS
# ============================================================

DB_PATH = os.getenv("DB_PATH", "pedidos.db")
MAX_NUMERO = 300
_local = threading.local()


def get_db():
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pedidos (
            numero  INTEGER PRIMARY KEY,
            cliente TEXT    NOT NULL,
            hora    TEXT    NOT NULL,
            status  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS itens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_pedido INTEGER NOT NULL,
            produto       TEXT    NOT NULL,
            quantidade    INTEGER NOT NULL,
            descricao     TEXT    NOT NULL DEFAULT '',
            FOREIGN KEY (numero_pedido) REFERENCES pedidos(numero) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS contador (
            id    INTEGER PRIMARY KEY CHECK (id = 1),
            valor INTEGER NOT NULL DEFAULT 1
        );
    """)
    row = conn.execute("SELECT valor FROM contador WHERE id = 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO contador (id, valor) VALUES (1, 1)")
    conn.commit()
    conn.close()


init_db()


# ============================================================
# STATUS
# ============================================================

STATUS_AGUARDANDO = "AGUARDANDO"
STATUS_PREPARO = "PREPARO"
STATUS_PRONTO = "PRONTO"
STATUS_ENTREGUE = "ENTREGUE"


# ============================================================
# WEBSOCKET
# ============================================================

class ConnectionManager:

    def __init__(self):
        self.connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, data: dict):

        mensagem = json.dumps(data)

        remover = []

        for connection in self.connections:

            try:
                await connection.send_text(mensagem)

            except Exception:
                remover.append(connection)

        for connection in remover:
            self.disconnect(connection)


manager = ConnectionManager()


# ============================================================
# FUNÇÕES DO BANCO
# ============================================================

def horario():
    return datetime.now().strftime("%H:%M")


def gerar_numero(db):
    row = db.execute("SELECT valor FROM contador WHERE id = 1").fetchone()
    numero = row["valor"]

    if numero > MAX_NUMERO:
        return None

    db.execute("UPDATE contador SET valor = ? WHERE id = 1", (numero + 1,))
    db.commit()

    return numero


def criar_pedido(cliente, itens, db):
    cliente = cliente.strip()
    if cliente == "":
        cliente = "Não informado"

    numero = gerar_numero(db)
    if numero is None:
        return None

    hora = horario()

    db.execute(
        "INSERT INTO pedidos (numero, cliente, hora, status) VALUES (?, ?, ?, ?)",
        (numero, cliente, hora, STATUS_AGUARDANDO)
    )

    for item in itens:
        if item["quantidade"] > 0:
            descricao = item.get("descricao", "")
            db.execute(
                "INSERT INTO itens (numero_pedido, produto, quantidade, descricao) VALUES (?, ?, ?, ?)",
                (numero, item["produto"], item["quantidade"], descricao)
            )

    db.commit()

    return {
        "numero": numero,
        "cliente": cliente,
        "hora": hora,
        "status": STATUS_AGUARDANDO,
        "itens": itens
    }


def localizar_pedido(numero, db):
    row = db.execute("SELECT * FROM pedidos WHERE numero = ?", (numero,)).fetchone()
    if row is None:
        return None

    itens_rows = db.execute(
        "SELECT produto, quantidade, descricao FROM itens WHERE numero_pedido = ?", (numero,)
    ).fetchall()

    return {
        "numero": row["numero"],
        "cliente": row["cliente"],
        "hora": row["hora"],
        "status": row["status"],
        "itens": [{"produto": r["produto"], "quantidade": r["quantidade"], "descricao": r["descricao"]} for r in itens_rows]
    }


def remover_pedido(numero, db):
    db.execute("DELETE FROM itens WHERE numero_pedido = ?", (numero,))
    db.execute("DELETE FROM pedidos WHERE numero = ?", (numero,))
    db.commit()


def listar_pedidos(db):
    rows = db.execute("SELECT * FROM pedidos WHERE status != ?", (STATUS_ENTREGUE,)).fetchall()
    resultado = []
    for row in rows:
        itens_rows = db.execute(
            "SELECT produto, quantidade, descricao FROM itens WHERE numero_pedido = ?", (row["numero"],)
        ).fetchall()
        resultado.append({
            "numero": row["numero"],
            "cliente": row["cliente"],
            "hora": row["hora"],
            "status": row["status"],
            "itens": [{"produto": r["produto"], "quantidade": r["quantidade"], "descricao": r["descricao"]} for r in itens_rows]
        })
    return resultado


# ============================================================
# ROTAS HTML
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def atendente(request: Request):

    return templates.TemplateResponse(

        "atendente.html",

        {

            "request": request,

            "produtos": PRODUTOS,

            "combos": COMBOS

        }

    )


@app.get("/cozinha", response_class=HTMLResponse)
async def cozinha(request: Request):

    return templates.TemplateResponse(

        "cozinha.html",

        {

            "request": request

        }

    )


@app.get("/painel", response_class=HTMLResponse)
async def painel(request: Request):

    return templates.TemplateResponse(

        "painel.html",

        {

            "request": request

        }

    )

# ============================================================
# AÇÕES DOS PEDIDOS
# ============================================================

async def enviar_lista(websocket: WebSocket):

    db = get_db()
    pedidos = listar_pedidos(db)

    await websocket.send_text(

        json.dumps({

            "tipo": "lista",

            "pedidos": pedidos

        })

    )


async def novo_pedido(cliente, itens):

    db = get_db()
    pedido = criar_pedido(cliente, itens, db)

    if pedido is None:
        await manager.broadcast({
            "tipo": "limite"
        })
        return

    await manager.broadcast({

        "tipo": "novo",

        "pedido": pedido

    })


async def iniciar_preparo(numero):

    db = get_db()
    pedido = localizar_pedido(numero, db)

    if pedido is None:
        return

    db.execute("UPDATE pedidos SET status = ? WHERE numero = ?", (STATUS_PREPARO, numero))
    db.commit()

    await manager.broadcast({

        "tipo": "preparo",

        "numero": numero

    })


async def marcar_pronto(numero):

    db = get_db()
    pedido = localizar_pedido(numero, db)

    if pedido is None:
        return

    db.execute("UPDATE pedidos SET status = ? WHERE numero = ?", (STATUS_PRONTO, numero))
    db.commit()

    await manager.broadcast({

        "tipo": "pronto",

        "numero": numero

    })


async def entregar_pedido(numero):

    db = get_db()
    remover_pedido(numero, db)

    await manager.broadcast({

        "tipo": "entregue",

        "numero": numero

    })


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await manager.connect(websocket)

    await enviar_lista(websocket)

    try:

        while True:

            dados = await websocket.receive_text()

            mensagem = json.loads(dados)

            tipo = mensagem["tipo"]

            if tipo == "novo":

                await novo_pedido(

                    mensagem["cliente"],

                    mensagem["itens"]

                )

            elif tipo == "preparo":

                await iniciar_preparo(

                    mensagem["numero"]

                )

            elif tipo == "pronto":

                await marcar_pronto(

                    mensagem["numero"]

                )

            elif tipo == "entregue":

                await entregar_pedido(

                    mensagem["numero"]

                )

    except WebSocketDisconnect:

        manager.disconnect(websocket)

# ============================================================
# OBSERVAÇÕES
# ============================================================

"""
Mensagens WebSocket

1) Novo pedido

{
    "tipo": "novo",
    "cliente": "Maria",
    "itens": [
        {
            "produto": "Pastel",
            "quantidade": 2
        },
        {
            "produto": "Refrigerante",
            "quantidade": 1
        }
    ]
}


2) Iniciar preparo

{
    "tipo": "preparo",
    "numero": 12
}


3) Pedido pronto

{
    "tipo": "pronto",
    "numero": 12
}


4) Pedido entregue

{
    "tipo": "entregue",
    "numero": 12
}


==============================================================


Mensagens enviadas pelo servidor


Lista inicial:

{
    "tipo": "lista",
    "pedidos": [...]
}


Novo pedido:

{
    "tipo": "novo",
    "pedido": {...}
}


Pedido em preparo:

{
    "tipo": "preparo",
    "numero": 12
}


Pedido pronto:

{
    "tipo": "pronto",
    "numero": 12
}


Pedido entregue:

{
    "tipo": "entregue",
    "numero": 12
}

"""