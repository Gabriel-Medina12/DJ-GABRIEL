import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import yt_dlp
from discord.ui import View
import asyncio
from collections import deque
import time


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Diccionario para almacenar los reproductores de música por servidor
music_players = {}

@bot.event
async def on_ready():
    print(f"Conectado como {bot.user}")
    check_inactivity.start()  # Iniciar la tarea de verificación de inactividad


class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.voice_client = None
        self.current_song = None
        self.queue = deque()  # Cola de canciones
        self.is_playing = False
        self.current_title = None
        self.current_thumbnail = None  # Variable para la portada
        self.last_activity = time.time()  # Tiempo de la última actividad

    async def connect(self):
        if self.ctx.voice_client is None:
            self.voice_client = await self.ctx.author.voice.channel.connect()
            await self.ctx.send(f"Me he unido a {self.ctx.author.voice.channel.name}!")
        else:
            self.voice_client = self.ctx.voice_client
        self.last_activity = time.time()  # Actualizar tiempo de actividad

    async def play_next(self):
        """Reproduce la siguiente canción en la cola"""
        if len(self.queue) > 0 and self.voice_client:
            # Hay canciones en la cola
            self.is_playing = True
            self.last_activity = time.time()  # Actualizar tiempo de actividad
            
            # Obtener la siguiente canción de la cola
            next_song = self.queue.popleft()
            url = next_song["url"]
            requester = next_song["requester"]
            thumbnail = next_song.get("thumbnail")
            title = next_song.get("title")
            
            # Reproducir la canción
            title = await self._play_song(url)
            if title:
                self.current_title = title
                self.current_thumbnail = thumbnail
                
                # Crear un embed con la portada
                embed = discord.Embed(
                    title="🎶 Reproduciendo ahora",
                    description=f"**{title}**\nSolicitada por {requester.mention}",
                    color=discord.Color.blue()
                )
                if thumbnail:
                    embed.set_thumbnail(url=thumbnail)
                
                # Enviar el mensaje con el embed
                await self.ctx.send(embed=embed)
                
                # Crear nuevos controles para la canción actual
                controls = MusicControls(self)
                await self.ctx.send(view=controls)
        else:
            # No hay más canciones en la cola
            self.is_playing = False
            self.current_title = None
            self.current_thumbnail = None

    async def add_to_queue(self, url, requester):
        """Añade una canción a la cola"""
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                # Si es búsqueda, tomar el primer resultado
                if 'entries' in info:
                    info = info['entries'][0]
                
                title = info.get('title', 'Desconocido')
                audio_url = info.get('url')
                thumbnail = info.get('thumbnail')

                # Añadir a la cola la URL directa
                self.queue.append({
                    "url": audio_url,  # URL de audio lista para usar
                    "title": title,
                    "thumbnail": thumbnail,
                    "requester": requester
                })
                
                return title
            except Exception as e:
                await self.ctx.send(f"Error al añadir a la cola: {str(e)}")
                return None

    async def _play_song(self, url):
        """Función interna para reproducir una canción"""
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Primero intentamos extraer la información
                info = ydl.extract_info(url, download=False)
                
                # Si es una búsqueda, tomamos el primer resultado
                if 'entries' in info:
                    info = info['entries'][0]
                
                # Obtenemos la URL de streaming
                audio_url = info.get('url')
                title = info.get('title', 'Desconocido')
                
                # Creamos el stream de audio
                self.current_song = discord.FFmpegPCMAudio(
                    audio_url,
                    before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
                )
                
                # Reproducir la canción y configurar el callback para cuando termine
                self.voice_client.play(
                    self.current_song, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.song_finished(e), bot.loop
                    )
                )
                
                return title
                    
            except Exception as e:
                await self.ctx.send(f"Error al reproducir: {str(e)}")
                return None

    async def song_finished(self, error):
        """Callback para cuando una canción termina"""
        if error:
            print(f"Error en la reproducción: {error}")
        
        # Reproducir la siguiente canción en la cola
        await self.play_next()

    async def play(self, url, requester):
        """Reproduce una canción o la añade a la cola"""
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        if not self.voice_client:
            await self.connect()
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch',
            'source_address': '0.0.0.0',
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                # Si es búsqueda, tomar el primer resultado
                if 'entries' in info:
                    info = info['entries'][0]
                
                title = info.get('title', 'Desconocido')
                audio_url = info.get('url')
                thumbnail = info.get('thumbnail')
                
                if self.is_playing:
                    # Ya hay una canción reproduciéndose, añadir a la cola
                    self.queue.append({
                        "url": audio_url,
                        "title": title,
                        "thumbnail": thumbnail,
                        "requester": requester
                    })
                    
                    position = len(self.queue)
                    
                    # Crear un embed para la cola
                    embed = discord.Embed(
                        title="🎵 Añadida a la cola",
                        description=f"**{title}**\nPosición #{position}\nSolicitada por {requester.mention}",
                        color=discord.Color.green()
                    )
                    if thumbnail:
                        embed.set_thumbnail(url=thumbnail)
                    
                    await self.ctx.send(embed=embed)
                    return None
                else:
                    # No hay canción reproduciéndose, reproducir inmediatamente
                    self.is_playing = True
                    self.current_title = title
                    self.current_thumbnail = thumbnail
                    await self._play_song(audio_url)
                    return {"title": title, "thumbnail": thumbnail}
                    
            except Exception as e:
                await self.ctx.send(f"Error al procesar la canción: {str(e)}")
                return None

    def pause(self):
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()

    def resume(self):
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()

    def stop(self):
        if self.voice_client:
            # Limpiar la cola
            self.queue.clear()
            
            # Detener la reproducción
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()
            
            # Desconectar
            asyncio.run_coroutine_threadsafe(self.voice_client.disconnect(), bot.loop)
            
            self.is_playing = False
            self.current_title = None
            self.current_thumbnail = None

    async def skip(self):
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()  # Esto activará el callback song_finished
            return True
        return False

    async def show_queue(self):
        """Muestra la cola actual"""
        self.last_activity = time.time()  # Actualizar tiempo de actividad
        if not self.queue and not self.current_title:
            return "La cola está vacía."
        
        embed = discord.Embed(
            title="🎵 Cola de reproducción",
            color=discord.Color.blue()
        )
        
        # Añadir la canción actual al principio
        if self.current_title:
            embed.add_field(
                name="Reproduciendo ahora:",
                value=f"**{self.current_title}**",
                inline=False
            )
            if self.current_thumbnail:
                embed.set_thumbnail(url=self.current_thumbnail)
        
        # Añadir las canciones en cola
        if self.queue:
            queue_text = ""
            for i, song in enumerate(self.queue, 1):
                queue_text += f"{i}. **{song['title']}** (solicitada por {song['requester'].mention})\n"
            
            embed.add_field(
                name="Próximas canciones:",
                value=queue_text,
                inline=False
            )
        
        return embed

    async def check_inactivity(self):
        """Verifica si el bot ha estado inactivo por más de 5 minutos"""
        if self.voice_client and self.voice_client.is_connected():
            current_time = time.time()
            # 300 segundos = 5 minutos
            if current_time - self.last_activity > 300:
                # Si ha pasado más de 5 minutos desde la última actividad
                await self.ctx.send("Me desconectaré debido a inactividad (5 minutos sin uso).")
                await self.voice_client.disconnect()
                return True
        return False


# Tarea periódica para verificar inactividad en todos los servidores
@tasks.loop(seconds=60)  # Verificar cada minuto
async def check_inactivity():
    for guild_id, player in list(music_players.items()):
        disconnected = await player.check_inactivity()
        if disconnected:
            # Eliminar el reproductor si se desconectó
            del music_players[guild_id]


class MusicControls(View):
    def __init__(self, player):
        super().__init__(timeout=None)  # Sin tiempo de expiración
        self.player = player

    @discord.ui.button(label="Pausar", style=discord.ButtonStyle.green)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.player.pause()
            await interaction.response.send_message("🎵 Música pausada.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Reanudar", style=discord.ButtonStyle.green)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.player.resume()
            await interaction.response.send_message("🎵 Música reanudada.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Saltar", style=discord.ButtonStyle.red)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            skipped = await self.player.skip()
            if skipped:
                await interaction.response.send_message("🎵 Saltando a la siguiente canción...", ephemeral=True)
            else:
                await interaction.response.send_message("No hay ninguna canción reproduciéndose.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Detener", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.player.stop()
            await interaction.response.send_message("🎵 Música detenida y cola limpiada.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)


@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Me he unido a {channel.name}")
        
        # Actualizar o crear un reproductor para este servidor
        guild_id = ctx.guild.id
        if guild_id not in music_players:
            music_players[guild_id] = MusicPlayer(ctx)
        music_players[guild_id].last_activity = time.time()
    else:
        await ctx.send("¡Debes estar en un canal de voz para usar este comando!")


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in music_players:
            del music_players[guild_id]
        await ctx.voice_client.disconnect()
        await ctx.send("Desconectado del canal de voz.")
    else:
        await ctx.send("No estoy conectado a ningún canal.")


@bot.command(aliases=['p'])
async def play(ctx, *, query):
    # Verifica que esté en canal de voz
    if not ctx.author.voice:
        await ctx.send("¡Debes estar en un canal de voz!")
        return

    # Obtener o crear el reproductor de música para este servidor
    guild_id = ctx.guild.id
    if guild_id not in music_players:
        music_players[guild_id] = MusicPlayer(ctx)
    
    player = music_players[guild_id]
    
    # Mostrar mensaje de carga
    loading_msg = await ctx.send("🔍 Buscando la canción...")
    
    # Reproducir la canción o añadirla a la cola
    result = await player.play(query, ctx.author)
    
    # Eliminar mensaje de carga
    await loading_msg.delete()
    
    # Si se reprodujo directamente (no se añadió a la cola)
    if result:
        # Enviar controles
        controls = MusicControls(player)
        
        # Crear un embed con la portada
        embed = discord.Embed(
            title="🎶 Reproduciendo ahora",
            description=f"**{result['title']}**\nSolicitada por {ctx.author.mention}",
            color=discord.Color.blue()
        )
        if result.get('thumbnail'):
            embed.set_thumbnail(url=result['thumbnail'])
        
        await ctx.send(embed=embed, view=controls)


@bot.command()
async def queue(ctx):
    """Muestra la cola actual de canciones"""
    guild_id = ctx.guild.id
    if guild_id in music_players:
        player = music_players[guild_id]
        queue_embed = await player.show_queue()
        
        if isinstance(queue_embed, str):
            await ctx.send(queue_embed)
        else:
            await ctx.send(embed=queue_embed)
    else:
        await ctx.send("No hay un reproductor de música activo en este servidor.")


@bot.command()
async def skip(ctx):
    """Salta a la siguiente canción en la cola"""
    guild_id = ctx.guild.id
    if guild_id in music_players:
        player = music_players[guild_id]
        skipped = await player.skip()
        if skipped:
            await ctx.send("🎵 Saltando a la siguiente canción...")
        else:
            await ctx.send("No hay ninguna canción reproduciéndose.")
    else:
        await ctx.send("No hay un reproductor de música activo en este servidor.")


@bot.command()
async def stop(ctx):
    """Detiene la reproducción y limpia la cola"""
    guild_id = ctx.guild.id
    if guild_id in music_players:
        player = music_players[guild_id]
        player.stop()
        await ctx.send("🎵 Reproducción detenida y cola limpiada.")
        # Eliminar el reproductor después de detener
        del music_players[guild_id]
    else:
        await ctx.send("No hay un reproductor de música activo en este servidor.")


# Asegurarse de que la tarea de verificación de inactividad se detenga cuando el bot se cierre
@bot.event
async def on_close():
    check_inactivity.cancel()


bot.run(TOKEN)