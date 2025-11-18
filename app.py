import tornado.ioloop
import tornado.web
import hashlib
import colorsys
import sqlite3
import os
from datetime import datetime

# === CONFIGURAÇÕES DE CAMINHOS ===
BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# === CONEXÃO COM O BANCO ===
con = sqlite3.connect(os.path.join(BASE_DIR, "KonVerse.db"), check_same_thread=False)
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

# === FUNÇÃO DE COR ===
def gerar_cor_do_nome(nome: str):
    hash_nome = int(hashlib.md5(nome.encode()).hexdigest(), 16)
    hue = (hash_nome % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.6, 0.9)
    return f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"

# === HANDLERS ===
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        usuario = self.get_secure_cookie("usuario")
        if usuario:
            self.redirect("/chat")
        else:
            erro = self.get_argument("erro", "")
            self.render("login.html", erro=erro)


class LoginHandler(tornado.web.RequestHandler):
    def post(self):
        nome = self.get_argument("nome", "").strip()
        senha = self.get_argument("senha", "").strip()

        if not nome or not senha:
            self.redirect("/?erro=Preencha%20todos%20os%20campos")
            return

        cur.execute("SELECT id, senha FROM usuarios WHERE nome = ?", (nome,))
        user = cur.fetchone()

        if user:
            user_id, senha_db = user
            if senha_db != senha:
                self.redirect("/?erro=Senha%20incorreta")
                return
        else:
            # cria conta automaticamente se não existir
            cur.execute("INSERT INTO usuarios (nome, senha) VALUES (?, ?)", (nome, senha))
            con.commit()
            user_id = cur.lastrowid

        # guarda o nome e id do usuário em cookie seguro
        self.set_secure_cookie("usuario", nome)
        self.set_secure_cookie("id_usuario", str(user_id))
        self.redirect("/chat")


class ChatHandler(tornado.web.RequestHandler):
    def get(self):
        usuario = self.get_secure_cookie("usuario")
        if not usuario:
            self.redirect("/")
            return
        self.render("index.html")


class MensagensHandler(tornado.web.RequestHandler):
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
            if not self._finished:
                self.set_status(500)
                self.write({"error": "Erro ao buscar mensagens"})
            # garante que a requisição termina aqui
            self.finish()

    def post(self):
        try:
            usuario = self.get_secure_cookie("usuario")
            id_usuario = self.get_secure_cookie("id_usuario")
            if not usuario or not id_usuario:
                self.set_status(403)
                self.write({"error": "Usuário não autenticado"})
                self.finish()
                return

            dados = tornado.escape.json_decode(self.request.body)
            texto = dados.get("texto", "").strip()

            if not texto:
                self.set_status(400)
                self.write({"error": "Mensagem vazia"})
                self.finish()
                return

            hora = datetime.now().strftime("%H:%M")
            cur.execute(
                "INSERT INTO mensagens (texto, id_usuario, hora) VALUES (?, ?, ?)",
                (texto, int(id_usuario), hora)
            )
            con.commit()

            self.write({"status": "ok"})
        except Exception as e:
            print("Erro ao enviar mensagem:", e)
            if not self._finished:
                self.set_status(500)
                self.write({"error": "Erro ao enviar mensagem"})
            self.finish()


def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/login", LoginHandler),
        (r"/chat", ChatHandler),
        (r"/mensagens", MensagensHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": STATIC_DIR}),
    ],
    template_path=TEMPLATES_DIR,
    static_path=STATIC_DIR,
    cookie_secret="uma_chave_muito_segura_aqui_123")  # altera pra algo aleatório


if __name__ == "__main__":
    app = make_app()
    app.listen(5050, address="0.0.0.0")

    ip_local = os.popen("hostname -I").read().split()[0]
    print(f"Servidor rodando em: http://{ip_local}:5050")

    tornado.ioloop.IOLoop.current().start()
