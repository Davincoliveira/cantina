1. Criar ambiente virtual

python -m venv venv

2. Ativar

Linux

source venv/bin/activate

Windows

venv\Scripts\activate

3. Instalar dependências

pip install -r requirements.txt

4. Executar

uvicorn app:app --reload

5. Acessar

Atendente

http://localhost:8000

Cozinha

http://localhost:8000/cozinha

Painel

http://localhost:8000/painel