import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

# Crear el bot con la intención de manejar miembros
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Conectar con la base de datos SQLite y crear tabla si no existe
conn = sqlite3.connect('creditos_sociales.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS puntos (
                    user_id TEXT PRIMARY KEY,
                    puntos INTEGER
                )''')
conn.commit()

# IDs importantes
ROL_ANCESTRAL_ID = 952981035921055804 
CANAL_LOGS_ID = 1299744357640835093
ROL_POCOS_PUNTOS_ID = 1299751149674696715

# Evento de inicio del bot
@bot.event
async def on_ready():
    await bot.tree.sync()  # Sincroniza los comandos slash con Discord
    print(f'Bot conectado como {bot.user}')

# Función para obtener los puntos de un usuario
def obtener_puntos(user_id):
    cursor.execute('SELECT puntos FROM puntos WHERE user_id = ?', (user_id,))
    resultado = cursor.fetchone()
    if resultado:
        return resultado[0]
    else:
        return 100  # Si no existe en la base de datos, comienza con 100 puntos

# Función para actualizar los puntos en la base de datos
def actualizar_puntos(user_id, puntos):
    puntos = max(0, puntos)  # Asegurarse de que los puntos no sean negativos
    cursor.execute('REPLACE INTO puntos (user_id, puntos) VALUES (?, ?)', (user_id, puntos))
    conn.commit()

# Función para actualizar el rol según los puntos
async def actualizar_rol_puntos(miembro: discord.Member):
    rol_pocos_puntos = miembro.guild.get_role(ROL_POCOS_PUNTOS_ID)
    puntos_actuales = obtener_puntos(str(miembro.id))
    
    if puntos_actuales <= 20:
        if rol_pocos_puntos not in miembro.roles:
            await miembro.add_roles(rol_pocos_puntos)
            embed = discord.Embed(
                title="Asignación de Rol",
                description=f"{miembro.mention}, se te ha asignado el rol debido a tu bajo puntaje.",
                color=discord.Color.red()
            )
            await miembro.send(embed=embed)
    else:
        if rol_pocos_puntos in miembro.roles:
            await miembro.remove_roles(rol_pocos_puntos)

# Verificador de permisos para los usuarios con el rol "Topo Ancestral"
def check_rol_ancestral():
    async def predicate(interaction: discord.Interaction) -> bool:
        user_roles = [role.id for role in interaction.user.roles]
        return ROL_ANCESTRAL_ID in user_roles
    return app_commands.check(predicate)

# Comando para mostrar los puntos del usuario
@bot.tree.command(name="puntos", description="Muestra tus puntos actuales.")
async def puntos(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    puntos_actuales = obtener_puntos(user_id)
    await interaction.response.send_message(
        f"{interaction.user.mention}, tienes {puntos_actuales} puntos.",
        ephemeral=True
    )

# Comando para sumar créditos a un usuario
@bot.tree.command(name="darcreditos", description="Añade créditos a un usuario con una razón.")
@check_rol_ancestral()
async def darcreditos(interaction: discord.Interaction, miembro: discord.Member, numero: int, razon: str = "No especificada"):
    user_id = str(miembro.id)
    puntos_actuales = obtener_puntos(user_id)
    nuevos_puntos = puntos_actuales + numero
    actualizar_puntos(user_id, nuevos_puntos)
    
    await log_creditos(interaction, miembro, numero, razon, "sumó")
    await interaction.response.send_message(f"{miembro.mention} ha recibido {numero} créditos.", ephemeral=True)
    await actualizar_rol_puntos(miembro)  # Actualizar roles según puntos

# Comando para restar créditos a un usuario
@bot.tree.command(name="quitarcreditos", description="Quita créditos a un usuario con una razón.")
@check_rol_ancestral()
async def quitarcreditos(interaction: discord.Interaction, miembro: discord.Member, numero: int, razon: str = "No especificada"):
    user_id = str(miembro.id)
    puntos_actuales = obtener_puntos(user_id)
    nuevos_puntos = puntos_actuales - numero
    nuevos_puntos = max(0, nuevos_puntos)  # Asegurarse de que los puntos no sean negativos
    actualizar_puntos(user_id, nuevos_puntos)
    
    await log_creditos(interaction, miembro, -numero, razon, "restó")
    await interaction.response.send_message(f"{miembro.mention} ha perdido {numero} créditos.", ephemeral=True)
    await actualizar_rol_puntos(miembro)  # Actualizar roles según puntos

# Comando para establecer créditos a un usuario
@bot.tree.command(name="establecercreditos", description="Establece una cantidad específica de créditos a un usuario.")
@check_rol_ancestral()
async def establecercreditos(interaction: discord.Interaction, miembro: discord.Member, numero: int):
    user_id = str(miembro.id)
    actualizar_puntos(user_id, numero)
    
    await interaction.response.send_message(f"{miembro.mention} ahora tiene {numero} créditos.", ephemeral=True)
    await actualizar_rol_puntos(miembro)  # Actualizar roles según puntos

# Comando para listar el top de usuarios con más puntos
@bot.tree.command(name="top", description="Muestra el top de usuarios con más puntos.")
async def top(interaction: discord.Interaction):
    guild = interaction.guild
    miembros_con_rol = [miembro for miembro in guild.members if ROL_ANCESTRAL_ID in [role.id for role in miembro.roles]]
    
    # Crear una lista para guardar el top de usuarios con sus puntos
    top_usuarios = []

    # Obtener los puntos de los miembros con el rol "topo ancestral" desde la base de datos
    for miembro in miembros_con_rol:
        puntos = obtener_puntos(str(miembro.id))
        top_usuarios.append((miembro, puntos))

    # Ordenar los usuarios por puntos
    top_usuarios = sorted(top_usuarios, key=lambda x: x[1], reverse=True)

    # Crear el embed
    embed = discord.Embed(title="Top de Créditos Sociales", color=discord.Color.blue())
    for miembro, puntos in top_usuarios:
        embed.add_field(name=miembro.display_name, value=f"{puntos} puntos", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=False)


# Comando para mostrar ayuda
@bot.tree.command(name="helpcreditos", description="Muestra la lista de comandos de créditos sociales.")
async def helpcreditos(interaction: discord.Interaction):
    canal = interaction.guild.get_channel(CANAL_LOGS_ID)
    if canal:
        embed = discord.Embed(
            title="Ayuda de Créditos Sociales",
            description="Lista de comandos disponibles para gestionar créditos sociales",
            color=discord.Color.green()
        )
        embed.add_field(name="/puntos", value="Muestra tus puntos actuales.", inline=False)
        embed.add_field(name="/darcreditos [User] [Puntos] [Razón]", value="Añade créditos a un usuario con una razón.", inline=False)
        embed.add_field(name="/quitarcreditos [User] [Puntos] [Razón]", value="Quita créditos a un usuario con una razón.", inline=False)
        embed.add_field(name="/establecercreditos [User] [Puntos]", value="Establece una cantidad específica de créditos a un usuario sin notificar", inline=False)
        embed.add_field(name="/top", value="Muestra el top de usuarios con más puntos.", inline=False)
        embed.set_footer(text=f"Solicitado por {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        await canal.send(embed=embed)
        await interaction.response.send_message("Se ha enviado la lista de comandos al canal de Créditos Sociales.", ephemeral=True)

# Función para registrar los cambios de créditos en el canal de logs
async def log_creditos(interaction, miembro, cantidad, razon, accion):
    canal = interaction.guild.get_channel(CANAL_LOGS_ID)
    puntos_actuales = obtener_puntos(str(miembro.id))  # Obtiene los puntos actuales del usuario
    embed = discord.Embed(title="Cambio de Créditos Sociales", color=discord.Color.red())
    embed.set_author(name=miembro.name, icon_url=miembro.avatar.url if miembro.avatar else None)
    embed.add_field(name="Usuario", value=miembro.mention, inline=True)
    embed.add_field(name="Acción", value=f"Se {accion} {cantidad} créditos", inline=True)
    embed.add_field(name="Razón", value=razon, inline=False)
    embed.add_field(name="Puntos Actuales", value=f"{puntos_actuales}", inline=True)  # Añadir puntos actuales
    embed.set_footer(text=f"Modificado por {interaction.user.name}")
    
    if canal:
        await canal.send(embed=embed)

# Manejo de errores de permisos
@darcreditos.error
@quitarcreditos.error
@establecercreditos.error
async def creditos_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("No tienes permisos para usar este comando.", ephemeral=True)

# Reemplaza 'TU_TOKEN_AQUÍ' con el token de tu bot
bot.run('')
