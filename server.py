import tornado.ioloop
import tornado.web
import hashlib
import colorsys
import sqlite3
from datetime import datetime

con = sqlite3.connect("KonVerse.db", check_same_thread=False)
cur = con.cursor()

cur.execute(""" 
    CREATE TABLE IF NOT EXISTS usuarios ( 
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        senha TEXT NOT NULL
    )
""")

cur.execute(""" 
    CREATE TABLE IF NOT EXISTS mensagens ( 
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        texto TEXT NOT NULL,
        id_usuario INTEGER NOT NULL,
        hora TEXT NOT NULL,
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
    )
""")

con.commit()


def gerar_cor_do_nome(nome: str):
    hash_nome = int(hashlib.md5(nome.encode()).hexdigest(), 16)
    hue = (hash_nome % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.6, 0.9)
    return f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"


class LoginHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self):
        self.set_status(204)
        self.finish()

    def post(self):
        try:
            dados = tornado.escape.json_decode(self.request.body)
            nome = dados.get("nome", "").strip()
            senha = dados.get("senha", "").strip()

            if not nome or not senha:
                self.set_status(400)
                self.write({"error": "Nome e senha são obrigatórios"})
                return

            cur.execute("SELECT id, senha FROM usuarios WHERE nome = ?", (nome,))
            user = cur.fetchone()

            if user:
                user_id, senha_db = user
                if senha_db != senha:
                    self.set_status(401)
                    self.write({"error": "Senha incorreta"})
                    return
            else:
                # Cria novo usuário
                cur.execute("INSERT INTO usuarios (nome, senha) VALUES (?, ?)", (nome, senha))
                con.commit()
                user_id = cur.lastrowid

            self.write({"status": "ok", "id_usuario": user_id, "nome": nome})

        except Exception as e:
            print("Erro no login:", e)
            self.set_status(500)
            self.write({"error": "Erro interno no servidor"})


class MensagensHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self):
        self.set_status(204)
        self.finish()

    def get(self):
        try:
            cur.execute("""
                SELECT mensagens.texto, mensagens.hora, usuarios.nome
                FROM mensagens
                JOIN usuarios ON mensagens.id_usuario = usuarios.id
                ORDER BY mensagens.id ASC
            """)
            dados = cur.fetchall()
            mensagens = [
                {"usuario": nome, "texto": texto, "hora": hora, "cor": gerar_cor_do_nome(nome)}
                for (texto, hora, nome) in dados
            ]
            self.write({"mensagens": mensagens})

        except Exception as e:
            print("Erro ao buscar mensagens:", e)
            self.set_status(500)
            self.write({"error": "Erro ao buscar mensagens"})

    def post(self):
        try:
            dados = tornado.escape.json_decode(self.request.body)
            id_usuario = dados.get("id_usuario")
            texto = dados.get("texto", "").strip()

            if not id_usuario or not texto:
                self.set_status(400)
                self.write({"error": "id_usuario e texto obrigatórios"})
                return

            hora = datetime.now().strftime("%H:%M")

            cur.execute(
                "INSERT INTO mensagens (texto, id_usuario, hora) VALUES (?, ?, ?)",
                (texto, id_usuario, hora)
            )
            con.commit()

            self.write({"status": "ok"})

        except Exception as e:
            print("Erro ao enviar mensagem:", e)
            self.set_status(500)
            self.write({"error": "Erro ao enviar mensagem"})



def make_app():
    return tornado.web.Application([
        (r"/login", LoginHandler),
        (r"/mensagens", MensagensHandler),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(5000)
    print("Servidor Tornado rodando em http://127.0.0.1:5000")
    tornado.ioloop.IOLoop.current().start()

