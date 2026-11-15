import os
import json
import requests
import threading
import time
from flask import Flask, request
from datetime import datetime, timedelta

app = Flask(__name__)

# =====================================================================
# CHAVES E CONFIGURAÇÕES (JÁ PREENCHIDAS COM OS DADOS DA JAQUE PINK)
# =====================================================================
TELEGRAM_BOT_TOKEN = "9270658230:AAEeAq0-qy100z-2ydEJzQF6C9gwkSOspFs"
VIP_JAQUE_GROUP_ID = "-1002069121485"
PREVIAS_JAQUE_GROUP_ID = "-1001994331287"
RENDER_URL_FIXA = "adm-jaquepink.onrender.com"

PUSHINPAY_API_TOKEN = "73774|DCDTM4JGmuvz4MS4g5vPHy2ucM54PkCeQEu7QA4y49fe526b"
ADMIN_ID = "7008304182"
VIP_PLAYBOX_GROUP_ID = "-1002019479469"

CHAMAR_NO_PRIVADO_AO_APROVAR = True

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
PUSHINPAY_API_URL = "https://api.pushinpay.com.br/api"

ARQUIVO_ESTADO = "estado_jaque.json"
lock_estado = threading.Lock()

usuarios = {}
transacoes_processadas = set()

# Controle do motor de remarketing nativo por PID do worker
_worker_pid = None
_lock_worker = threading.Lock()
_ultima_checagem_assinaturas = 0.0

# =====================================================================
# MÍDIAS DO FUNIL (JÁ PREENCHIDAS COM SEUS 4 FILE_IDs)
# =====================================================================
VIDEO_1_GALERIA = "BAACAgEAAxkBAAMCavoug55fcXjT1El_G-E9Qt7SNlcAAqEIAAKHW9BH-qFU6cQ_aDg9BA"
VIDEO_2_D4 = "BAACAgEAAxkBAAMDavoujCrKcf0PqyFqWfmLTTixV34AAqIIAAKHW9BHKijEHmQ7N2s9BA"
VIDEO_3_PLAYBOX_OFERTA = "BAACAgEAAxkBAAMFavowGAKrK-hWzVhtrREdnFf-fSMAAqQIAAKHW9BHvUOd7s-Qrjw9BA"
VIDEO_4_UNICORNIO = "BAACAgEAAxkBAAMEavoulZGdWHGb31O8Kj77i8ZW4AYAAqMIA AKHW9BHvYPbp0FwBXg9BA"

# =====================================================================
# TABELA DE PLANOS, ORDER BUMP E DESCONTOS DE RENOVAÇÃO
# =====================================================================
PRECO_BUMP_PLAYBOX = 7.90

PLANOS = {
    "7d": {
        "nome": "1 Semana (7 dias)",
        "dias": 7,
        "preco": 9.90,
        "preco_renov": 9.40,   # 5% OFF
        "desconto_txt": "5% OFF"
    },
    "30d": {
        "nome": "1 Mês (30 dias)",
        "dias": 30,
        "preco": 19.90,
        "preco_renov": 16.90,  # 15% OFF
        "desconto_txt": "15% OFF"
    },
    "vit": {
        "nome": "Acesso Vitalício",
        "dias": None,
        "preco": 59.90,
        "preco_renov": 47.90,  # 20% OFF
        "desconto_txt": "20% OFF"
    }
}

# Tempos do remarketing em segundos: 4m -> 6m -> 12m -> 25m -> 3h (infinito)
TEMPOS_REMARKETING_SEGUNDOS = [240, 360, 720, 1500, 10800]

ETAPAS_COM_REMARKETING = {
    "INICIO_SEM_CLIQUE",
    "VENDO_BUMP_PLAYBOX",
    "AGUARDANDO_PIX",
    "RENOVANDO_PIX",
    "EXPIROU_RENOVACAO"
}

# =====================================================================
# COPYS DO FUNIL DE VENDAS
# =====================================================================
TEXTO_OFERTA_JAQUE = (
    "🦄 **VIP OFICIAL — JAQUE PINK (SEM CENSURA)** 🔥\n\n"
    "Você acabou de ver a prévia, mas o que acontece nos vídeos completos lá dentro é outro nível. No meu **VIP Exclusivo** você assiste na íntegra:\n\n"
    "🚕 **Pagando a corrida do Uber de outras formas** (gravado no sigilo sem cortes)\n"
    "🔞 **Encontros reais com desconhecidos** fazendo tudo o que você imagina\n"
    "🤫 **Os vídeos proibidos com o titio dela** que não podem vazar aqui fora\n"
    "📂 **Galeria completa + atualizações toda semana**\n\n"
    "⚡ *Liberação automática e imediata após o PIX.*\n\n"
    "👇 **ESCOLHA SEU PLANO ABAIXO PARA ENTRAR AGORA:**"
)

TEXTO_BUMP_PLAYBOX = (
    "💣 **ESPERA! LIBEREI UM BÔNUS SECRETO SÓ PARA VOCÊ...**\n\n"
    "Antes de gerar seu PIX da Jaque Pink, você pode adicionar o **VIP VITALÍCIO DA PLAYBOX** por apenas **+ R$ 7,90**!\n\n"
    "Lá dentro você leva um acervo gigante e separado com:\n"
    "🔞 **Casadas no sigilo absoluto**\n"
    "📸 **Flagras reais e câmeras escondidas**\n"
    "📂 **Vazados raros + Drive Secreto com +400 vídeos amadores**\n"
    "✅ **Acesso Vitalício** (sem mensalidade)\n\n"
    "👇 **TOQUE ABAIXO PARA ESCOLHER COMO DESEJA FINALIZAR:**"
)

TEXTO_INSTRUCOES_PIX = (
    "✅ **Como pagar seu PIX Copia e Cola e entrar na hora:**\n\n"
    "1️⃣ - Toque no botão azul **Copiar Chave Pix 🗒** abaixo\n"
    "2️⃣ - Abra o aplicativo do seu banco\n"
    "3️⃣ - Entre na área **PIX ➔ PIX Copia e Cola**, cole o código e finalize\n"
    "4️⃣ - Volte aqui e toque em **Já fiz o pagamento! ✅**\n\n"
    "⬇️ **COPIE SEU CÓDIGO PIX ABAIXO** ⬇️"
)

COPYS_REMARKETING_ROTACAO = [
    (
        "🚕 **VOCÊ NÃO VIU COMO ESSA CORRIDA DO UBER TERMINOU...**\n\n"
        "A Jaque Pink deixou a câmera gravando tudo no banco de trás e o vídeo completo está liberado agora no VIP.\n\n"
        "👇 **Finalize seu acesso antes que o link expire:**"
    ),
    (
        "🤫 **OS VÍDEOS PROIBIDOS COM O TITIO ESTÃO LÁ DENTRO...**\n\n"
        "Conteúdo pesado, sem cortes e sem censura que jamais vai aparecer no grupo grátis. Sua vaga ainda está reservada!\n\n"
        "👇 **Toque abaixo e entre agora:**"
    ),
    (
        "🔥 **ENCONTROS REAIS COM DESCONHECIDOS NO SIGILO!**\n\n"
        "Mais de centenas de vídeos completos da Jaque Pink + atualizações novas toda semana direto no seu celular.\n\n"
        "👇 **Libere seu acesso imediato via PIX:**"
    ),
    (
        "👀 **OLHA A GALERIA QUE ACABOU DE SER ATUALIZADA NO VIP...**\n\n"
        "Enquanto você pensa, o pessoal já está assistindo tudo sem tarjas e sem cortes. Planos a partir de R$ 9,90!\n\n"
        "👇 **Garanta sua entrada agora:**"
    )
]

COPY_REMARKETING_UNICORNIO = (
    "🦄 **ÚLTIMO AVISO DO UNICÓRNIO — SEU ACESSO ESTÁ EXPIRANDO!** 🚨\n\n"
    "Você está a um clique de entrar no **VIP da Jaque Pink**, mas ainda não concluiu seu acesso.\n\n"
    "Não fique de fora dos vídeos completos no Uber, com desconhecidos e os arquivos secretos com o titio.\n\n"
    "⚡ **A liberação é automática em 5 segundos após o PIX!**\n\n"
    "👇 **TOQUE NO BOTÃO ABAIXO E ENTRE AGORA:**"
)

COPY_REMARKETING_PLAYBOX_6 = (
    "💣 **QUER LEVAR O ACERVO COMPLETO DA PLAYBOX JUNTO?** 🔥\n\n"
    "Além do VIP da Jaque Pink, você pode desbloquear o **VIP Vitalício da PlayBox** (Casadas no sigilo, câmeras escondidas e +400 vazados) por apenas **+ R$ 7,90**!\n\n"
    "👇 **Aproveite essa condição antes que saia do ar:**"
)

COPYS_REMARKETING_BUMP_PLAYBOX = [
    (
        "💣 **VOCÊ DEIXOU O VIP VITALÍCIO DA PLAYBOX PARA TRÁS...**\n\n"
        "Por apenas **+ R$ 7,90**, você leva junto com o VIP da Jaque Pink o acesso **VITALÍCIO** ao acervo completo da PlayBox (casadas no sigilo, câmeras escondidas e +400 vazados).\n\n"
        "👇 **Escolha abaixo para gerar seu PIX e entrar nos dois grupos agora:**"
    ),
    (
        "🔥 **2 GRUPOS VIPS PELO PREÇO DE 1 — ÚLTIMA CHANCE!**\n\n"
        "Seu plano da Jaque Pink já está selecionado. Adicione o **VIP Vitalício da PlayBox** por apenas **R$ 7,90** a mais e receba os dois links na hora!\n\n"
        "👇 **Toque abaixo para finalizar seu PIX:**"
    ),
    (
        "🔞 **CASADAS NO SIGILO + CÂMERAS ESCONDIDAS POR + R$ 7,90!**\n\n"
        "Essa oferta de combo só aparece aqui antes do pagamento. Depois que sair dessa tela, o VIP da PlayBox volta para o valor normal.\n\n"
        "👇 **Garanta o combo completo ou finalize apenas o VIP da Jaque:**"
    ),
    (
        "⏳ **SEU COMBO PROMOCIONAL ESTÁ PRESTES A EXPIRAR!**\n\n"
        "Finalize agora com o **VIP Vitalício da PlayBox** incluso ou siga apenas com o VIP da Jaque Pink.\n\n"
        "👇 **Selecione uma opção abaixo para gerar o PIX:**"
    )
]


# =====================================================================
# PERSISTÊNCIA DE ESTADO EM DISCO
# =====================================================================
def salvar_estado():
    with lock_estado:
        try:
            dados = {
                "usuarios": {str(k): v for k, v in usuarios.items()},
                "transacoes": list(transacoes_processadas)
            }
            with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar estado: {e}", flush=True)


def carregar_estado():
    global usuarios, transacoes_processadas
    if not os.path.exists(ARQUIVO_ESTADO):
        return
    try:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        usuarios = {int(k): v for k, v in dados.get("usuarios", {}).items()}
        transacoes_processadas = set(dados.get("transacoes", []))
    except Exception as e:
        print(f"Erro ao carregar estado: {e}", flush=True)


# =====================================================================
# FUNÇÕES DE ENVIO TELEGRAM (COM FALLBACK TRIPLO ANTI-FALHA)
# =====================================================================
def _remover_estilos_markup(markup):
    if not markup or "inline_keyboard" not in markup:
        return markup
    novo_teclado = []
    for linha in markup["inline_keyboard"]:
        nova_linha = []
        for btn in linha:
            btn_limpo = {k: v for k, v in btn.items() if k != "style"}
            nova_linha.append(btn_limpo)
        novo_teclado.append(nova_linha)
    return {"inline_keyboard": novo_teclado}


def enviar_mensagem(chat_id, texto, markup=None):
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = markup
    try:
        req = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=15)
        if req.status_code != 200:
            payload_sem_md = {"chat_id": chat_id, "text": texto}
            if markup:
                payload_sem_md["reply_markup"] = markup
            req2 = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload_sem_md, timeout=15)
            if req2.status_code != 200 and markup:
                payload_sem_estilo = {"chat_id": chat_id, "text": texto, "reply_markup": _remover_estilos_markup(markup)}
                req3 = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload_sem_estilo, timeout=15)
                if req3.status_code != 200:
                    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": texto}, timeout=15)
    except Exception as e:
        print(f"Exceção sendMessage: {e}", flush=True)


def enviar_video(chat_id, video_id, legenda=None, markup=None):
    payload = {"chat_id": chat_id, "video": video_id, "parse_mode": "Markdown"}
    if legenda:
        payload["caption"] = legenda
    if markup:
        payload["reply_markup"] = markup
    try:
        req = requests.post(f"{TELEGRAM_API_URL}/sendVideo", json=payload, timeout=30)
        if req.status_code == 200:
            return True

        print(f"⚠️ Erro sendVideo ({req.status_code}): {req.text}", flush=True)

        if legenda:
            payload_sem_md = dict(payload)
            payload_sem_md.pop("parse_mode", None)
            req2 = requests.post(f"{TELEGRAM_API_URL}/sendVideo", json=payload_sem_md, timeout=30)
            if req2.status_code == 200:
                return True

        payload_anim = {"chat_id": chat_id, "animation": video_id}
        if legenda:
            payload_anim["caption"] = legenda
        if markup:
            payload_anim["reply_markup"] = markup
        req3 = requests.post(f"{TELEGRAM_API_URL}/sendAnimation", json=payload_anim, timeout=30)
        if req3.status_code == 200:
            return True

        if legenda:
            enviar_mensagem(chat_id, legenda, markup)
            return True

    except Exception as e:
        print(f"❌ Exceção sendVideo: {e}", flush=True)
        if legenda:
            enviar_mensagem(chat_id, legenda, markup)
    return False


def responder_clique_botao(callback_query_id):
    try:
        requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": callback_query_id}, timeout=5)
    except Exception:
        pass


def gerar_link_convite_unico(group_id):
    try:
        res = requests.post(
            f"{TELEGRAM_API_URL}/createChatInviteLink",
            json={"chat_id": group_id, "member_limit": 1},
            timeout=15
        ).json()
        return res.get("result", {}).get("invite_link")
    except Exception as e:
        print(f"Erro ao gerar link convite ({group_id}): {e}", flush=True)
        return None


def remover_usuario_vip(user_id):
    try:
        requests.post(
            f"{TELEGRAM_API_URL}/banChatMember",
            json={"chat_id": VIP_JAQUE_GROUP_ID, "user_id": user_id},
            timeout=10
        )
        time.sleep(1)
        requests.post(
            f"{TELEGRAM_API_URL}/unbanChatMember",
            json={"chat_id": VIP_JAQUE_GROUP_ID, "user_id": user_id, "only_if_banned": True},
            timeout=10
        )
        print(f"🚫 Assinante {user_id} removido do VIP Jaque Pink por vencimento.", flush=True)
    except Exception as e:
        print(f"Erro ao remover usuário vencido ({user_id}): {e}", flush=True)


# =====================================================================
# INTEGRAÇÃO PUSHIN PAY (GERAR E CONSULTAR)
# =====================================================================
def gerar_pix_pushinpay(valor_em_reais, chat_id):
    headers = {
        "Authorization": f"Bearer {PUSHINPAY_API_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    valor_centavos = int(round(float(valor_em_reais) * 100))
    webhook_dinamico = f"https://{RENDER_URL_FIXA}/webhook/pushinpay?chat_id={chat_id}"

    payload = {
        "value": valor_centavos,
        "webhook_url": webhook_dinamico
    }

    try:
        req = requests.post(f"{PUSHINPAY_API_URL}/pix/cashIn", json=payload, headers=headers, timeout=15)
        if req.status_code in [200, 201]:
            resposta_json = req.json()
            codigo = resposta_json.get("qr_code") or resposta_json.get("pix_copia_e_cola")
            tx_id = resposta_json.get("id")
            return codigo, tx_id, None
        else:
            return None, None, f"Código {req.status_code} - {req.text}"
    except Exception as e:
        return None, None, str(e)


def consultar_pagamento_pushinpay(tx_id):
    if not tx_id:
        return False
    headers = {
        "Authorization": f"Bearer {PUSHINPAY_API_TOKEN}",
        "Accept": "application/json"
    }
    for rota in [f"{PUSHINPAY_API_URL}/transactions/{tx_id}", f"{PUSHINPAY_API_URL}/transaction/{tx_id}"]:
        try:
            req = requests.get(rota, headers=headers, timeout=15)
            if req.status_code == 200:
                dados = req.json()
                if isinstance(dados.get("data"), dict):
                    dados = dados["data"]
                status = str(dados.get("status", "")).lower()
                if status in ["paid", "approved", "concluded", "settled"]:
                    return True
                return False
        except Exception as e:
            print(f"Erro ao consultar {rota}: {e}", flush=True)
    return False


# =====================================================================
# AGENDAMENTO E DISPARO DO REMARKETING (PURO PYTHON / IMUNE A FORK)
# =====================================================================
def obter_intervalo_segundos(contagem):
    idx = min(int(contagem), len(TEMPOS_REMARKETING_SEGUNDOS) - 1)
    return TEMPOS_REMARKETING_SEGUNDOS[idx]


def programar_proximo_remarketing(chat_id, etapa, contagem, atraso_customizado=None):
    garantir_loop_worker()
    chat_id = int(chat_id)
    info = usuarios.setdefault(chat_id, {})
    info["status"] = etapa
    info["rmk_contagem"] = int(contagem)
    espera = int(atraso_customizado) if atraso_customizado is not None else obter_intervalo_segundos(contagem)
    info["proximo_rmk_em"] = time.time() + espera
    salvar_estado()
    print(f"⏰ [RMK PROGRAMADO] Lead: {chat_id} | Etapa: {etapa} | Passo: {contagem + 1} | Em: {espera}s", flush=True)


def _montar_botoes_remarketing(chat_id, tipo_funil):
    user_info = usuarios.get(chat_id, {})
    plano_cod = user_info.get("plano_pendente") or user_info.get("plano_ativo") or "7d"
    dados_plano = PLANOS.get(plano_cod, PLANOS["7d"])

    if tipo_funil in ["EXPIROU_RENOVACAO", "RENOVANDO_PIX"]:
        return {
            "inline_keyboard": [
                [{"text": f"🔄 Renovar 7 dias ({PLANOS['7d']['desconto_txt']}) - R$ {PLANOS['7d']['preco_renov']:.2f}", "callback_data": "renovar_7d"}],
                [{"text": f"🔥 Renovar 1 Mês ({PLANOS['30d']['desconto_txt']}) - R$ {PLANOS['30d']['preco_renov']:.2f}", "callback_data": "renovar_30d"}],
                [{"text": f"👑 Vitalício ({PLANOS['vit']['desconto_txt']}) - R$ {PLANOS['vit']['preco_renov']:.2f}", "callback_data": "renovar_vit"}]
            ]
        }

    if tipo_funil == "INICIO_SEM_CLIQUE":
        return {
            "inline_keyboard": [
                [{"text": "🔥 1 Semana (7 dias) — R$ 9,90", "callback_data": "escolher_7d"}],
                [{"text": "💎 1 Mês (30 dias) — R$ 19,90", "callback_data": "escolher_30d"}],
                [{"text": "👑 Acesso Vitalício — R$ 59,90", "callback_data": "escolher_vit"}]
            ]
        }

    valor_combo = dados_plano["preco"] + PRECO_BUMP_PLAYBOX
    return {
        "inline_keyboard": [
            [{"text": f"💣 Jaque + VIP PlayBox — R$ {valor_combo:.2f}", "callback_data": "fechar_combo"}],
            [{"text": f"🦄 Apenas VIP Jaque ({dados_plano['nome']}) — R$ {dados_plano['preco']:.2f}", "callback_data": "fechar_solo"}]
        ]
    }


def _escolher_video_sequencia_padrao(contagem):
    num_envio = contagem + 1

    # 1º envio e a cada 4 vídeos -> Vídeo Unicórnio
    if num_envio == 1 or num_envio % 4 == 0:
        return VIDEO_4_UNICORNIO, COPY_REMARKETING_UNICORNIO

    # 6º vídeo (e múltiplos de 6 que não caíram no 4) -> Oferta VIP PlayBox
    if num_envio % 6 == 0:
        return VIDEO_3_PLAYBOX_OFERTA, COPY_REMARKETING_PLAYBOX_6

    # Demais envios -> Intercala Vídeo 1 (Galeria) e Vídeo 2 (D4) variando as copys
    comuns_anteriores = sum(
        1 for i in range(1, num_envio)
        if i != 1 and (i % 4 != 0) and (i % 6 != 0)
    )
    copy_escolhida = COPYS_REMARKETING_ROTACAO[comuns_anteriores % len(COPYS_REMARKETING_ROTACAO)]

    if comuns_anteriores % 2 == 0:
        return VIDEO_1_GALERIA, copy_escolhida
    else:
        return VIDEO_2_D4, copy_escolhida


def executar_disparo_remarketing(chat_id, tipo_funil, contagem):
    chat_id = int(chat_id)
    print(f"🔥 [RMK ENVIANDO AGORA] Lead: {chat_id} | Etapa: {tipo_funil} | Passo: {contagem + 1}", flush=True)
    try:
        markup = _montar_botoes_remarketing(chat_id, tipo_funil)

        if tipo_funil == "VENDO_BUMP_PLAYBOX":
            copy_bump = COPYS_REMARKETING_BUMP_PLAYBOX[contagem % len(COPYS_REMARKETING_BUMP_PLAYBOX)]
            enviar_video(chat_id, VIDEO_3_PLAYBOX_OFERTA, copy_bump, markup)
        else:
            video_id, legenda = _escolher_video_sequencia_padrao(contagem)
            enviar_video(chat_id, video_id, legenda, markup)

    except Exception as e:
        print(f"❌ Erro ao disparar remarketing ({chat_id}): {e}", flush=True)


# =====================================================================
# ENTREGA DO PIX (SEM IMAGEM + RESET DE REMARKETING)
# =====================================================================
def entregar_pix_completo(chat_id, valor_reais, plano_codigo, inclui_playbox=False, eh_renovacao=False):
    chat_id = int(chat_id)
    enviar_mensagem(chat_id, "⏳ *Gerando sua chave PIX exclusiva, aguarde...*")
    codigo_pix, tx_id, erro = gerar_pix_pushinpay(valor_reais, chat_id)

    if codigo_pix:
        user_info = usuarios.setdefault(chat_id, {})
        user_info["tx_id"] = tx_id
        user_info["plano_pendente"] = plano_codigo
        user_info["inclui_playbox_pendente"] = inclui_playbox
        user_info["eh_renovacao_pendente"] = eh_renovacao

        if user_info.get("status") == "VIP_ATIVO":
            nova_etapa = "RENOVANDO_PIX"
        elif user_info.get("status") == "EXPIROU_RENOVACAO" or eh_renovacao:
            nova_etapa = "EXPIROU_RENOVACAO"
        else:
            nova_etapa = "AGUARDANDO_PIX"

        enviar_mensagem(chat_id, TEXTO_INSTRUCOES_PIX)
        time.sleep(0.4)

        markup_pix = {
            "inline_keyboard": [
                [
                    {
                        "text": "Já fiz o pagamento! ✅",
                        "callback_data": "verificar_pagamento",
                        "style": "success"
                    }
                ],
                [
                    {
                        "text": "Copiar Chave Pix 🗒",
                        "copy_text": {"text": codigo_pix},
                        "style": "primary"
                    }
                ]
            ]
        }
        enviar_mensagem(chat_id, f"`{codigo_pix}`", markup_pix)

        # Reseta sempre o tempo do remarketing para o início (4 min -> Vídeo Unicórnio)
        programar_proximo_remarketing(chat_id, nova_etapa, 0)
    else:
        enviar_mensagem(chat_id, f"❌ *Erro de comunicação com o banco. Tente novamente!*\n`{erro}`")


# =====================================================================
# LIBERAÇÃO DE ACESSO APÓS PAGAMENTO CONFIRMADO
# =====================================================================
def processar_pagamento_aprovado(chat_id, tx_id=None):
    chat_id = int(chat_id)

    if tx_id:
        tx_norm = str(tx_id).lower()
        if tx_norm in transacoes_processadas:
            return True
        transacoes_processadas.add(tx_norm)

    user_info = usuarios.setdefault(chat_id, {})
    plano_cod = user_info.get("plano_pendente") or user_info.get("plano_ativo") or "7d"
    inclui_playbox = bool(user_info.get("inclui_playbox_pendente", False))
    dados_plano = PLANOS.get(plano_cod, PLANOS["7d"])

    agora = datetime.now()
    dias_plano = dados_plano["dias"]

    if dias_plano is None:
        nova_expiracao = None
        texto_validade = "👑 **Validade:** Acesso Vitalício (para sempre!)"
    else:
        exp_atual_str = user_info.get("expira_em")
        base_tempo = agora
        if exp_atual_str and user_info.get("status") in ["VIP_ATIVO", "RENOVANDO_PIX"]:
            try:
                exp_atual = datetime.fromisoformat(exp_atual_str)
                if exp_atual > agora:
                    base_tempo = exp_atual
            except Exception:
                pass
        dt_exp = base_tempo + timedelta(days=dias_plano)
        nova_expiracao = dt_exp.isoformat()
        texto_validade = f"📅 **Válido até:** {dt_exp.strftime('%d/%m/%Y às %H:%M')}"

    user_info["status"] = "VIP_ATIVO"
    user_info["plano_ativo"] = plano_cod
    user_info["expira_em"] = nova_expiracao
    user_info["aviso_nivel"] = 0
    user_info["tx_id"] = None
    user_info["proximo_rmk_em"] = None
    user_info["inclui_playbox_pendente"] = False
    user_info["eh_renovacao_pendente"] = False
    salvar_estado()

    link_jaque = gerar_link_convite_unico(VIP_JAQUE_GROUP_ID) or "LINK_VIP_JAQUE_AQUI"
    mensagem_entrega = (
        f"🎉 **PAGAMENTO CONFIRMADO COM SUCESSO!**\n\n"
        f"🦄 **Plano liberado:** {dados_plano['nome']}\n"
        f"{texto_validade}\n\n"
        f"👇 **TOQUE ABAIXO PARA ENTRAR NO VIP DA JAQUE PINK:**\n"
        f"🔥 [ACESSAR VIP JAQUE PINK AGORA]({link_jaque})"
    )

    if inclui_playbox:
        link_playbox = gerar_link_convite_unico(VIP_PLAYBOX_GROUP_ID) or "LINK_VIP_PLAYBOX_AQUI"
        mensagem_entrega += (
            f"\n\n💣 **BÔNUS PLAYBOX VITALÍCIO LIBERADO:**\n"
            f"👑 [ACESSAR VIP PLAYBOX AGORA]({link_playbox})"
        )

    enviar_mensagem(chat_id, mensagem_entrega)
    return True


# =====================================================================
# RÉGUA DE RENOVAÇÃO ANTECIPADA COM DESCONTO + REMOÇÃO AUTOMÁTICA
# =====================================================================
def verificar_assinaturas_background():
    agora = datetime.now()
    alterou = False

    for chat_id, info in list(usuarios.items()):
        if info.get("status") not in ["VIP_ATIVO", "RENOVANDO_PIX"]:
            continue

        exp_str = info.get("expira_em")
        if not exp_str:
            continue

        try:
            dt_exp = datetime.fromisoformat(exp_str)
        except Exception:
            continue

        horas_restantes = (dt_exp - agora).total_seconds() / 3600.0
        aviso_nivel = int(info.get("aviso_nivel", 0))
        plano_atual = info.get("plano_ativo", "7d")
        dados_plano = PLANOS.get(plano_atual, PLANOS["7d"])

        if horas_restantes <= 0:
            remover_usuario_vip(chat_id)
            info["status"] = "EXPIROU_RENOVACAO"
            info["rmk_contagem"] = 1
            info["proximo_rmk_em"] = time.time() + obter_intervalo_segundos(1)
            alterou = True

            markup_exp = _montar_botoes_remarketing(chat_id, "EXPIROU_RENOVACAO")
            texto_expirou = (
                "🚨 **SEU ACESSO AO VIP DA JAQUE PINK EXPIROU!**\n\n"
                "Sua assinatura venceu e você foi removido automaticamente do grupo VIP.\n\n"
                "🎁 **Mas liberei um desconto exclusivo para você voltar agora mesmo:**\n"
                f"• **1 Semana:** R$ {PLANOS['7d']['preco_renov']:.2f} ({PLANOS['7d']['desconto_txt']})\n"
                f"• **1 Mês:** R$ {PLANOS['30d']['preco_renov']:.2f} ({PLANOS['30d']['desconto_txt']})\n"
                f"• **Vitalício:** R$ {PLANOS['vit']['preco_renov']:.2f} ({PLANOS['vit']['desconto_txt']})\n\n"
                "👇 **Escolha abaixo para gerar seu PIX e voltar na hora:**"
            )
            enviar_video(chat_id, VIDEO_4_UNICORNIO, texto_expirou, markup_exp)

        elif horas_restantes <= 1.0 and aviso_nivel < 3:
            info["aviso_nivel"] = 3
            alterou = True
            markup_aviso = {
                "inline_keyboard": [
                    [{"text": f"⚡ Renovar {dados_plano['nome']} ({dados_plano['desconto_txt']}) — R$ {dados_plano['preco_renov']:.2f}", "callback_data": f"renovar_{plano_atual}"}],
                    [{"text": f"👑 Migrar Vitalício (20% OFF) — R$ {PLANOS['vit']['preco_renov']:.2f}", "callback_data": "renovar_vit"}]
                ]
            }
            enviar_mensagem(
                chat_id,
                f"⏳ **ÚLTIMA HORA! SEU VIP VENCE EM MENOS DE 60 MINUTOS!**\n\n"
                f"Renove agora com **{dados_plano['desconto_txt']}** antes que o sistema remova você automaticamente do grupo da Jaque Pink:",
                markup_aviso
            )

        elif horas_restantes <= 6.0 and aviso_nivel < 2:
            info["aviso_nivel"] = 2
            alterou = True
            markup_aviso = {
                "inline_keyboard": [
                    [{"text": f"🔄 Renovar {dados_plano['nome']} ({dados_plano['desconto_txt']}) — R$ {dados_plano['preco_renov']:.2f}", "callback_data": f"renovar_{plano_atual}"}],
                    [{"text": f"🔥 1 Mês (15% OFF) — R$ {PLANOS['30d']['preco_renov']:.2f}", "callback_data": "renovar_30d"}],
                    [{"text": f"👑 Vitalício (20% OFF) — R$ {PLANOS['vit']['preco_renov']:.2f}", "callback_data": "renovar_vit"}]
                ]
            }
            enviar_mensagem(
                chat_id,
                f"⚠️ **FALTAM MENOS DE 6 HORAS PARA SEU VIP VENCER!**\n\n"
                f"Garanta sua renovação antecipada com **{dados_plano['desconto_txt']}** (os novos dias são somados ao tempo que você ainda tem!):",
                markup_aviso
            )

        elif horas_restantes <= 24.0 and aviso_nivel < 1:
            info["aviso_nivel"] = 1
            alterou = True
            enviar_mensagem(
                chat_id,
                f"🦄 **SEU VIP DA JAQUE PINK VENCE EM MENOS DE 24 HORAS!**\n\n"
                f"Para você não perder nenhum vídeo novo, já gerei seu **PIX de renovação com {dados_plano['desconto_txt']}** (de R$ {dados_plano['preco']:.2f} por **R$ {dados_plano['preco_renov']:.2f}**).\n\n"
                f"💡 *Se preferir mudar para o Mensal (15% OFF) ou Vitalício (20% OFF), toque em uma das opções abaixo:*",
                {
                    "inline_keyboard": [
                        [{"text": f"🔥 Trocar para 1 Mês (15% OFF) — R$ {PLANOS['30d']['preco_renov']:.2f}", "callback_data": "renovar_30d"}],
                        [{"text": f"👑 Trocar para Vitalício (20% OFF) — R$ {PLANOS['vit']['preco_renov']:.2f}", "callback_data": "renovar_vit"}]
                    ]
                }
            )
            entregar_pix_completo(chat_id, dados_plano["preco_renov"], plano_atual, inclui_playbox=False, eh_renovacao=True)

    if alterou:
        salvar_estado()


# =====================================================================
# LOOP PRINCIPAL DO WORKER (RODA A CADA 5 SEGUNDOS SEM FALHAR)
# =====================================================================
def _loop_vigilante_worker():
    global _ultima_checagem_assinaturas
    pid_atual = os.getpid()
    print(f"🚀 Motor de Remarketing iniciado com sucesso no PID {pid_atual}!", flush=True)

    while True:
        try:
            agora_ts = time.time()
            houve_alteracao = False

            for chat_id, info in list(usuarios.items()):
                etapa = info.get("status")
                prox_ts = info.get("proximo_rmk_em")

                if etapa in ETAPAS_COM_REMARKETING and prox_ts is not None:
                    if agora_ts >= float(prox_ts):
                        contagem_atual = int(info.get("rmk_contagem", 0))
                        proxima_contagem = contagem_atual + 1
                        info["rmk_contagem"] = proxima_contagem
                        info["proximo_rmk_em"] = agora_ts + obter_intervalo_segundos(proxima_contagem)
                        houve_alteracao = True

                        threading.Thread(
                            target=executar_disparo_remarketing,
                            args=(chat_id, etapa, contagem_atual),
                            daemon=True
                        ).start()

            if houve_alteracao:
                salvar_estado()

            if agora_ts - _ultima_checagem_assinaturas >= 60:
                _ultima_checagem_assinaturas = agora_ts
                verificar_assinaturas_background()

        except Exception as e:
            print(f"❌ Erro no loop vigilante: {e}", flush=True)

        time.sleep(5)


def garantir_loop_worker():
    global _worker_pid
    pid_atual = os.getpid()
    if _worker_pid != pid_atual:
        with _lock_worker:
            if _worker_pid != pid_atual:
                _worker_pid = pid_atual
                t = threading.Thread(target=_loop_vigilante_worker, daemon=True)
                t.start()


@app.before_request
def antes_de_qualquer_requisicao():
    garantir_loop_worker()


# =====================================================================
# FUNIL DE ENTRADA (/START E APROVAÇÃO AUTOMÁTICA DE PRÉVIAS)
# =====================================================================
def iniciar_fluxo_boas_vindas(chat_id):
    garantir_loop_worker()
    chat_id = int(chat_id)
    usuarios[chat_id] = {
        "status": "INICIO_SEM_CLIQUE",
        "tx_id": None,
        "rmk_contagem": 0,
        "proximo_rmk_em": time.time() + obter_intervalo_segundos(0),
        "plano_pendente": "7d",
        "inclui_playbox_pendente": False
    }
    salvar_estado()
    print(f"⏰ [RMK PROGRAMADO] Lead: {chat_id} | Etapa: INICIO_SEM_CLIQUE | Passo: 1 | Em: 240s", flush=True)

    def envio_inicial():
        enviar_video(chat_id, VIDEO_1_GALERIA)
        time.sleep(2)

        markup_planos = {
            "inline_keyboard": [
                [{"text": "🔥 1 Semana (7 dias) — R$ 9,90", "callback_data": "escolher_7d"}],
                [{"text": "💎 1 Mês (30 dias) — R$ 19,90", "callback_data": "escolher_30d"}],
                [{"text": "👑 Acesso Vitalício — R$ 59,90", "callback_data": "escolher_vit"}]
            ]
        }
        enviar_video(chat_id, VIDEO_2_D4, TEXTO_OFERTA_JAQUE, markup_planos)

    threading.Thread(target=envio_inicial, daemon=True).start()


# =====================================================================
# ROTAS WEB E WEBHOOKS
# =====================================================================
@app.route("/", methods=["GET"])
def home():
    garantir_loop_worker()
    return f"Bot VIP Jaque Pink Ativo! | Worker PID: {_worker_pid} | Leads: {len(usuarios)}", 200


@app.route("/status", methods=["GET"])
def status_debug():
    garantir_loop_worker()
    agora = time.time()
    fila = []
    for cid, info in usuarios.items():
        prox = info.get("proximo_rmk_em")
        fila.append({
            "chat_id": cid,
            "etapa": info.get("status"),
            "proximo_passo": int(info.get("rmk_contagem", 0)) + 1,
            "dispara_em_segundos": round(prox - agora, 1) if prox else None
        })
    return {
        "worker_pid": _worker_pid,
        "total_leads": len(usuarios),
        "fila_remarketing": fila
    }, 200


@app.route("/setup", methods=["GET"])
def setup_webhook():
    garantir_loop_worker()
    webhook_url = f"https://{RENDER_URL_FIXA}/webhook/telegram/{TELEGRAM_BOT_TOKEN}"
    payload = {
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query", "chat_join_request"]
    }
    resposta = requests.post(f"{TELEGRAM_API_URL}/setWebhook", json=payload)
    return f"Status do Webhook Jaque Pink: {resposta.json()}", 200


@app.route("/webhook/pushinpay", methods=["POST", "GET"])
def pushinpay_webhook():
    garantir_loop_worker()
    dados = request.get_json(force=True, silent=True)
    if not dados:
        dados = request.form.to_dict() if request.form else {}

    if not dados and not request.args:
        return {"status": "Webhook PushinPay Jaque Pink ativo!"}, 200

    status_bruto = dados.get("status") or (dados.get("data", {}).get("status") if isinstance(dados.get("data"), dict) else "")
    status = str(status_bruto).lower()

    tx_id = dados.get("id") or (dados.get("data", {}).get("id") if isinstance(dados.get("data"), dict) else None)
    chat_id = request.args.get("chat_id") or dados.get("external_reference")

    if not chat_id and tx_id:
        tx_norm = str(tx_id).lower()
        for cid, info in usuarios.items():
            if str(info.get("tx_id", "")).lower() == tx_norm:
                chat_id = cid
                break

    if status in ["paid", "approved", "concluded", "settled"] and chat_id:
        processar_pagamento_aprovado(chat_id, tx_id)

    return {"status": "ok"}, 200


@app.route(f"/webhook/telegram/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    garantir_loop_worker()
    update = request.get_json(silent=True)
    if not update:
        return {"status": "ok"}, 200

    if "message" in update:
        chat_id = int(update["message"]["chat"]["id"])
        texto = update["message"].get("text", "")

        if texto.startswith("/start"):
            iniciar_fluxo_boas_vindas(chat_id)

        elif texto.startswith("/testar_rmk") and str(chat_id) == ADMIN_ID:
            info = usuarios.get(chat_id)
            if not info or info.get("status") not in ETAPAS_COM_REMARKETING:
                enviar_mensagem(chat_id, "⚠️ Envie /start primeiro para entrar em uma etapa do funil.")
            else:
                etapa = info.get("status")
                cont = int(info.get("rmk_contagem", 0))
                programar_proximo_remarketing(chat_id, etapa, cont, atraso_customizado=3)
                enviar_mensagem(chat_id, f"🧪 **Teste armado!** O remarketing #{cont + 1} da etapa `{etapa}` vai disparar em **3 segundos**.")

    elif "callback_query" in update:
        query = update["callback_query"]
        chat_id = int(query["message"]["chat"]["id"])
        botao = query["data"]
        responder_clique_botao(query["id"])

        if botao in ["escolher_7d", "escolher_30d", "escolher_vit"]:
            plano_cod = botao.replace("escolher_", "")
            dados_plano = PLANOS[plano_cod]
            valor_combo = dados_plano["preco"] + PRECO_BUMP_PLAYBOX

            user_info = usuarios.setdefault(chat_id, {})
            user_info["plano_pendente"] = plano_cod
            programar_proximo_remarketing(chat_id, "VENDO_BUMP_PLAYBOX", 0)

            def enviar_order_bump():
                markup_bump = {
                    "inline_keyboard": [
                        [{"text": f"💣 SIM! {dados_plano['nome']} + PlayBox — R$ {valor_combo:.2f}", "callback_data": "fechar_combo"}],
                        [{"text": f"🦄 Apenas VIP Jaque Pink — R$ {dados_plano['preco']:.2f}", "callback_data": "fechar_solo"}]
                    ]
                }
                enviar_video(chat_id, VIDEO_3_PLAYBOX_OFERTA, TEXTO_BUMP_PLAYBOX, markup_bump)

            threading.Thread(target=enviar_order_bump, daemon=True).start()

        elif botao in ["fechar_combo", "fechar_solo"]:
            user_info = usuarios.setdefault(chat_id, {})
            plano_cod = user_info.get("plano_pendente", "7d")
            dados_plano = PLANOS.get(plano_cod, PLANOS["7d"])

            inclui_playbox = (botao == "fechar_combo")
            valor_final = dados_plano["preco"] + (PRECO_BUMP_PLAYBOX if inclui_playbox else 0.0)

            threading.Thread(
                target=entregar_pix_completo,
                args=(chat_id, valor_final, plano_cod, inclui_playbox, False),
                daemon=True
            ).start()

        elif botao in ["renovar_7d", "renovar_30d", "renovar_vit"]:
            plano_cod = botao.replace("renovar_", "")
            dados_plano = PLANOS[plano_cod]
            valor_desconto = dados_plano["preco_renov"]

            threading.Thread(
                target=entregar_pix_completo,
                args=(chat_id, valor_desconto, plano_cod, False, True),
                daemon=True
            ).start()

        elif botao == "verificar_pagamento":
            tx_id = usuarios.get(chat_id, {}).get("tx_id")

            def checar_pix():
                if not tx_id:
                    enviar_mensagem(chat_id, "⚠️ *Nenhum PIX ativo encontrado.* Escolha um plano acima para gerar seu código.")
                    return

                enviar_mensagem(chat_id, "🔍 *Verificando seu pagamento junto ao banco, aguarde...*")
                if consultar_pagamento_pushinpay(tx_id):
                    processar_pagamento_aprovado(chat_id, tx_id)
                else:
                    enviar_mensagem(
                        chat_id,
                        "⏳ *Pagamento ainda não identificado!*\n\nO banco ainda não confirmou o seu PIX. Assim que concluir no aplicativo do banco, toque em **Já fiz o pagamento! ✅** novamente."
                    )

            threading.Thread(target=checar_pix, daemon=True).start()

    elif "chat_join_request" in update:
        req_entrada = update["chat_join_request"]
        grupo_id = str(req_entrada["chat"]["id"])
        user_id = int(req_entrada["from"]["id"])

        if grupo_id == PREVIAS_JAQUE_GROUP_ID:
            try:
                requests.post(
                    f"{TELEGRAM_API_URL}/approveChatJoinRequest",
                    json={"chat_id": grupo_id, "user_id": user_id},
                    timeout=10
                )
            except Exception as e:
                print(f"Erro ao aprovar entrada prévias Jaque ({user_id}): {e}", flush=True)

            if CHAMAR_NO_PRIVADO_AO_APROVAR and user_id not in usuarios:
                iniciar_fluxo_boas_vindas(user_id)

    return {"status": "ok"}, 200


carregar_estado()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
