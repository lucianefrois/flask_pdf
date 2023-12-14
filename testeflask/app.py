import subprocess
from flask import Flask, render_template, request, make_response, redirect, url_for
import mysql.connector
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import pyautogui as pa, time
import logging
from flask import render_template

app = Flask(__name__)

# Configurações do MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'tcc_top3'

def conectar_mysql():
    return mysql.connector.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )

def fechar_conexao_mysql(connection):
    if connection.is_connected():
        connection.close()

@app.route('/')
def index():
    connection = conectar_mysql()
    cursor = connection.cursor(dictionary=True)

    # Obtém todos os clientes ou despachantes
    cursor.execute("SELECT DISTINCT Cliente_Despachante FROM relatorio_individual")
    nomes = cursor.fetchall()

    fechar_conexao_mysql(connection)

    return render_template('index.html', nomes=nomes)


@app.route('/pagamentos', methods=['GET', 'POST'])
def pagamentos():
    if request.method == 'POST':
        nome = request.form['nome']
        return redirect(url_for('gerar_pdf', nome=nome))

    connection = conectar_mysql()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT Cliente_Despachante FROM relatorio_individual")
    nomes = cursor.fetchall()
    fechar_conexao_mysql(connection)

    return render_template('pdf.html', nomes=nomes)

@app.route('/gerar_pdf', methods=['POST'])
def gerar_pdf():
    nome = request.form['nome']

    connection = conectar_mysql()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.id_entrada AS ID_Entrada, sc.data_entrada AS Data_Servico, c.nome_cliente AS Cliente_Despachante,
               tv.nome AS Tipo_Veículo, sc.placa AS Placa, sc.valor_servico AS Valor_Serviço,
               e.valor AS Valor_Total, e.status_p AS Pago, op.nome_op_caixa AS Nome_Op_Caixa
        FROM entrada e
        JOIN servico_cliente sc ON e.id_servico_cliente = sc.id_servico_cliente
        JOIN cliente c ON sc.id_cliente = c.id_cliente
        JOIN tipo_veiculo tv ON sc.id_tipo_veiculo_cliente = tv.id_tipo_veiculo
        LEFT JOIN op_caixa op ON sc.id_op_caixa_cliente = op.id_op_caixa
        WHERE (e.status_p IS NULL OR e.status_p = 0) AND c.nome_cliente = %s
    """, (nome,))
    pagamentos = cursor.fetchall()
    fechar_conexao_mysql(connection)

    pagos = [{'Placa': p['Placa'], 'Tipo_Veículo': p['Tipo_Veículo'], 'Valor_Serviço': p['Valor_Serviço'], 'Valor_Total': p['Valor_Total']} for p in pagamentos if p['Pago']]
    nao_pagos = [{'Placa': p['Placa'], 'Tipo_Veículo': p['Tipo_Veículo'], 'Valor_Serviço': p['Valor_Serviço'], 'Valor_Total': p['Valor_Total']} for p in pagamentos if not p['Pago']]

    response = gerar_pdf_individuo(nome, pagos, nao_pagos)
    return response

def gerar_pdf_individuo(nome, pagos, nao_pagos):
    response = make_response()
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={nome}_pagamentos.pdf'

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    pdf.drawString(100, 800, f"Pagamentos de {nome}")
    pdf.drawString(100, 780, "Pagos:")
    for i, item in enumerate(pagos, start=1):
        pdf.drawString(120, 780 - (i * 20), f"{i}. Placa: {item['Placa']}, Tipo Veículo: {item['Tipo_Veículo']}, Valor Serviço: {item['Valor_Serviço']}, Valor Total: {item['Valor_Total']}")

    pdf.drawString(100, 740, "Não Pagos:")
    for i, item in enumerate(nao_pagos, start=1):
        pdf.drawString(120, 740 - (i * 20), f"{i}. Placa: {item['Placa']}, Tipo Veículo: {item['Tipo_Veículo']}, Valor Serviço: {item['Valor_Serviço']}, Valor Total: {item['Valor_Total']}")

    pdf.save()

    buffer.seek(0)
    response.data = buffer.read()

    return response

@app.route('/gerar_pdf_geral', methods=['POST'])
def gerar_pdf_geral():
    data_inicio = request.form['data_inicio']
    data_fim = request.form['data_fim']

    try:
        # Converter as datas de string para objetos datetime
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d')
    except ValueError:
        return "Erro: Formato de data inválido. Use o formato YYYY-MM-DD."

    connection = conectar_mysql()
    cursor = connection.cursor(dictionary=True)
    
    # Consulta na view relatorio_geral
    cursor.execute("""
        SELECT 
            `ID Entrada`,
            `Data_Servico`,
            `Cliente_Despachante`,
            `Valor_Serviço`,
            `Pago`
        FROM relatorio_geral
        WHERE `Data_Servico` BETWEEN %s AND %s
    """, (data_inicio, data_fim))
    
    pagamentos = cursor.fetchall()
    fechar_conexao_mysql(connection)

    # Gerar o PDF com os dados filtrados
    response = gerar_pdf_geral_individuo(data_inicio, data_fim, pagamentos)
    return response

def gerar_pdf_geral_individuo(data_inicio, data_fim, pagamentos):
    response = make_response()
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=relatorio_geral_{data_inicio}_{data_fim}.pdf'

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    pdf.drawString(100, 800, f"Relatório Geral de Pagamentos de {data_inicio} a {data_fim}")
    pdf.drawString(100, 780, "Detalhes:")
    
    for i, item in enumerate(pagamentos, start=1):
        pdf.drawString(120, 780 - (i * 20), f"{i}. Cliente: {item['Cliente_Despachante']}, Data Serviço: {item['Data_Servico']}, Valor Serviço: {item['Valor_Serviço']}, Pago: {'Sim' if item['Pago'] else 'Não'}")

    pdf.save()
    subprocess.run(["AutoHotKey.exe", "automacao.ahk"])
    buffer.seek(0)
    response.data = buffer.read()

    return response
@app.route('/automatizar_processo', methods=['GET'])
def automatizar_processo():
    try:
        logging.info("Iniciando automação...")
        # Seu código de automação usando PyAutoGUI vai aqui
        pa.hotkey('ctrl', 't')
        pa.write('https://web.whatsapp.com/')
        pa.press('ENTER')
        time.sleep(15)
        pa.hotkey('ctrl', 'alt', 'n')
        time.sleep(5)
        pa.write('Link')
        pa.press('ENTER')

        logging.info("Automação concluída com sucesso.")
        return "Processo de automação concluído com sucesso"
    except Exception as e:
        logging.error(f"Erro ao acionar o processo de automação! Detalhes: {str(e)}")
        return "Erro ao acionar o processo de automação!"
    
# ...

# ...

@app.route('/adicionar_cliente', methods=['GET', 'POST'])
def adicionar_cliente():
    if request.method == 'POST':
        nome = request.form['nome_cliente']
        doc = request.form['doc_cliente']
        tipo = request.form['tipo_cliente']

        connection = conectar_mysql()
        cursor = connection.cursor()

        # Insere novo cliente no banco de dados
        cursor.execute("INSERT INTO cliente (nome_cliente, doc_cliente, tipo_cliente) VALUES (%s, %s, %s)", (nome, doc, tipo))
        connection.commit()

        # Obtém todos os clientes para exibição na página (atualizado)
        cursor.execute("SELECT * FROM cliente")
        clientes = cursor.fetchall()
        fechar_conexao_mysql(connection)

        return render_template('cliente.html', clientes=clientes)

    connection = conectar_mysql()
    cursor = connection.cursor()

    # Obtém todos os clientes para exibição na página
    cursor.execute("SELECT * FROM cliente")
    clientes = cursor.fetchall()
    fechar_conexao_mysql(connection)

    return render_template('cliente.html', clientes=clientes)


# ...




if __name__ == '__main__':
    app.run(debug=True ,threaded=True)

