import discord
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput, Button
import asyncio
import traceback
import os
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Adicionado para garantir acesso a guilds e roles
bot = commands.Bot(command_prefix='!', intents=intents)

# ID do dono da loja
OWNER_ID = 1271573735383760980

# IDs dos cargos que podem acessar o canal
ALLOWED_ROLES = [
    1355689622608543855,  # Cargo Permitido 1
    1355689621438333091,  # Cargo Permitido 2
    1355689620515586111,  # Cargo Permitido 3
    1343290302214967387   # Cargo Permitido 4
]

# IDs dos cargos que não podem acessar o canal
RESTRICTED_ROLES = [
    1355689627356237924,  # Cargo Restrito 1
    1355689626299400274,  # Cargo Restrito 2
    1355689625397760210,  # Cargo Restrito 3
    1355899744383139913   # Cargo Restrito 4
]

# Tabela de Preços
prices_normal = {
    100: 4.80,
    200: 9.60,
    300: 14.40,
    400: 19.20,
    500: 24.00,
    600: 28.80,
    700: 33.60,
    800: 38.40,
    900: 43.20,
    1000: 48.00
}

prices_discount = {k: v * 0.8 for k, v in prices_normal.items()}

def calculate_price(quantity):
    closest_key = min(prices_normal.keys(), key=lambda x: abs(x - quantity))
    price_per_robux = prices_normal[closest_key] / closest_key
    return round(price_per_robux * quantity, 2)

class PurchaseTypeDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Robux via Gamepass",
                description="Crie um gamepass e receba seus Robux em até 6 dias após a compra.",
                emoji="🎮"
            ),
            discord.SelectOption(
                label="Robux via Grupo",
                description="Receba na hora, desde que esteja no grupo há pelo menos 14 dias e tenha saldo disponível.",
                emoji="👥"
            ),
            discord.SelectOption(
                label="Gamepass Gift",
                description="Entrega rápida para qualquer jogo que permita envio de presentes.",
                emoji="🎁"
            )
        ]
        super().__init__(
            placeholder="Selecione o tipo de compra",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):
        selected_option = self.values[0]
        await interaction.response.send_modal(RobloxFormModal(selected_option.lower()))

class RobloxFormModal(Modal):
    def __init__(self, purchase_type):
        super().__init__(title=f"Compra de Robux - {purchase_type.capitalize()}")
        self.purchase_type = purchase_type

        self.username = TextInput(
            label="Nome do Roblox",
            placeholder="Digite seu nome de usuário...",
            required=True
        )
        self.quantity = TextInput(
            label="Quantidade de Robux",
            placeholder="Ex: 500",
            required=True
        )
        self.contact = TextInput(
            label="Email ou Telefone",
            placeholder="Ex: exemplo@email.com ou +55 11 99999-9999",
            required=True
        )

        self.add_item(self.username)
        self.add_item(self.quantity)
        self.add_item(self.contact)

    async def on_submit(self, interaction):
        username = self.username.value

        try:
            quantity = int(self.quantity.value)  # Trata erro se não for número
        except ValueError:
            await interaction.response.send_message(
                "Por favor, insira apenas números na quantidade de Robux.",
                ephemeral=True
            )
            return

        contact = self.contact.value

        if quantity < 40 or quantity > 10000:
            await interaction.response.send_message(
                "Quantidade inválida. O mínimo é 40 Robux e o máximo é 10.000 Robux.",
                ephemeral=True
            )
            return

        price = calculate_price(quantity)
        embed = discord.Embed(
            title="Verificando Disponibilidade",
            description=f"Seu pedido está sendo processado:\n"
                       f"• Nome de Usuário: {username}\n"
                       f"• Quantidade: {quantity} Robux\n"
                       f"• Preço Total: R$ {price:.2f}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Esta mensagem será removida em 5 segundos.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await asyncio.sleep(5)

        # Verifica se já existe um carrinho para o usuário
        existing_channel = discord.utils.get(interaction.guild.text_channels, name=f"carrinho-{interaction.user.name.lower()}")
        if existing_channel:
            await interaction.followup.send(
                f"Você já possui um carrinho ativo! Acesse-o aqui: [Carrinho]({existing_channel.mention})",
                ephemeral=True
            )
            return

        # Cria a CartView sem criar o carrinho diretamente
        cart_view = CartView(username, quantity, price, self.purchase_type, contact)
        await interaction.followup.send("Seu carrinho foi criado!", view=cart_view, ephemeral=True)

class CartView(View):
    def __init__(self, username, quantity, price, purchase_type, contact):
        super().__init__(timeout=None)
        self.username = username
        self.quantity = quantity
        self.price = price
        self.purchase_type = purchase_type
        self.contact = contact

    @discord.ui.button(label="Ir para o Carrinho", style=discord.ButtonStyle.success)
    async def open_cart_button(self, interaction, button):
        try:
            # Responde imediatamente à interação para evitar timeout
            await interaction.response.defer(ephemeral=True)

            # Verificar se o carrinho já existe
            existing_channel = discord.utils.get(interaction.guild.text_channels, name=f"carrinho-{interaction.user.name.lower()}")
            if existing_channel:
                channel_link = f"https://discord.com/channels/{interaction.guild.id}/{existing_channel.id}"
                await interaction.followup.send(
                    f"Você já possui um carrinho! Acesse-o aqui: [Carrinho]({channel_link})",
                    ephemeral=True
                )
                return

            # Criar o canal do carrinho
            category = interaction.channel.category  # Usa a mesma categoria do canal atual
            cart_channel = await interaction.guild.create_text_channel(
                name=f"carrinho-{interaction.user.name.lower()}",
                category=category
            )

            # Negar acesso ao @everyone
            await cart_channel.set_permissions(interaction.guild.default_role, read_messages=False)

            # Adicionar permissões para o comprador
            await cart_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)

            # Configurar permissões para os cargos permitidos
            for role_id in ALLOWED_ROLES:
                role = interaction.guild.get_role(role_id)
                if role:
                    await cart_channel.set_permissions(role, read_messages=True, send_messages=True)

            # Bloquear cargos restritos explicitamente
            for role_id in RESTRICTED_ROLES:
                role = interaction.guild.get_role(role_id)
                if role:
                    await cart_channel.set_permissions(role, read_messages=False)

            # Gerar o link do canal do carrinho
            channel_link = f"https://discord.com/channels/{interaction.guild.id}/{cart_channel.id}"

            # Notificar o usuário que o carrinho foi criado
            await interaction.followup.send(
                f"Seu carrinho foi criado com sucesso! Acesse-o aqui: [Carrinho]({channel_link})",
                ephemeral=True
            )

            # Exibir painel de pagamento no canal do carrinho
            payment_embed = discord.Embed(
                title="Detalhes da Compra",
                description="Confirme os detalhes da sua compra:",
                color=discord.Color.blue()
            )
            payment_embed.add_field(
                name="Informações do Pedido",
                value=(
                    f"• Nome de Usuário: {self.username}\n"
                    f"• Quantidade: {self.quantity} Robux\n"
                    f"• Preço Total: R$ {self.price:.2f}"
                ),
                inline=False
            )
            payment_embed.add_field(
                name="Termos e Condições",
                value=(
                    "Ao realizar uma compra, você concorda com nossos termos de serviço.\n"
                    "Consulte nossa política de reembolso antes de prosseguir."
                ),
                inline=False
            )
            payment_view = PaymentView(cart_channel)
            await cart_channel.send(embed=payment_embed, view=payment_view)

        except Exception as e:
            traceback.print_exc()  # Log mais detalhado
            await interaction.followup.send(
                f"Ocorreu um erro ao criar o carrinho. Por favor, tente novamente.\nErro: {str(e)}",
                ephemeral=True
            )

class PaymentView(View):
    def __init__(self, cart_channel):
        super().__init__(timeout=None)
        self.cart_channel = cart_channel

        button_crypto = Button(label="Cripto", style=discord.ButtonStyle.secondary)
        button_credit_card = Button(label="Cartão de Crédito", style=discord.ButtonStyle.secondary)
        button_pix = Button(label="Pix", style=discord.ButtonStyle.secondary)
        button_gift_card = Button(label="Gift Card", style=discord.ButtonStyle.secondary)
        button_delete = Button(label="Deletar Carrinho", style=discord.ButtonStyle.danger)

        button_crypto.callback = self.crypto_callback
        button_credit_card.callback = self.credit_card_callback
        button_pix.callback = self.pix_callback
        button_gift_card.callback = self.gift_card_callback
        button_delete.callback = self.delete_cart_callback

        self.add_item(button_crypto)
        self.add_item(button_credit_card)
        self.add_item(button_pix)
        self.add_item(button_gift_card)
        self.add_item(button_delete)

    async def crypto_callback(self, interaction):
        embed = discord.Embed(
            title="Pagamento via Cripto",
            description="Um moderador estará disponível em breve para finalizar o pagamento!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Obrigado por escolher a Robux Express!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def credit_card_callback(self, interaction):
        embed = discord.Embed(
            title="Pagamento via Cartão de Crédito",
            description="Um moderador estará disponível em breve para finalizar o pagamento!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Obrigado por escolher a Robux Express!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def pix_callback(self, interaction):
        embed = discord.Embed(
            title="Pagamento via Pix",
            description="Um moderador estará disponível em breve para finalizar o pagamento!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Obrigado por escolher a Robux Express!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def gift_card_callback(self, interaction):
        await interaction.response.send_modal(GiftCardModal())

    async def delete_cart_callback(self, interaction):
        await interaction.response.send_message("Seu carrinho foi excluído.", ephemeral=True)
        await self.cart_channel.delete()

class GiftCardModal(Modal):
    def __init__(self):
        super().__init__(title="Informações do Gift Card")
        
        self.source = TextInput(
            label="De onde é o Gift Card?",
            placeholder="Ex: Roblox Store, Outra Empresa...",
            required=True
        )
        self.code = TextInput(
            label="Código do Gift Card",
            placeholder="Digite o código completo...",
            required=True
        )

        self.add_item(self.source)
        self.add_item(self.code)

    async def on_submit(self, interaction):
        source = self.source.value
        code = self.code.value

        await interaction.response.send_message(
            "Aguardando aprovação de moderador para prosseguir.",
            ephemeral=True
        )

        owner = await bot.fetch_user(OWNER_ID)
        await owner.send(
            f"Novo pedido de Gift Card!\n"
            f"• Fonte: {source}\n"
            f"• Código: {code}"
        )

@bot.command()
async def start(ctx):
    embed = discord.Embed(
        title="Robux Express - Painel de Compras",
        description="Escolha uma opção abaixo para iniciar sua compra.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="Opções de Compra:",
        value=(
            "• Robux via Gamepass: Crie um gamepass e receba seus Robux em até 6 dias após a compra.\n"
            "• Robux via Grupo: Receba na hora, desde que esteja no grupo há pelo menos 14 dias e tenha saldo disponível.\n"
            "• Gamepass Gift: Entrega rápida para qualquer jogo que permita envio de presentes."
        ),
        inline=False
    )
    embed.add_field(
        name="Termos e Condições:",
        value=(
            "Ao realizar uma compra, você concorda com nossos termos de serviço.\n"
            "Consulte nossa política de reembolso antes de prosseguir."
        ),
        inline=False
    )
    embed.set_footer(text="Robux Express © 2025")

    view = View(timeout=None)
    dropdown = PurchaseTypeDropdown()
    view.add_item(dropdown)

    await ctx.send(embed=embed, view=view)

# Execução do Bot
bot.run(os.getenv("DISCORD_TOKEN"))  # Aqui vai buscar o token da variável de ambiente