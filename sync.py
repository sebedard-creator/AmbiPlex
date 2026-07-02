import os
import time
import logging
import asyncio
from plexapi.server import PlexServer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncModule")

class PlexSynchronizer:
    def __init__(self, plex_url: str, plex_token: str, master_client_name: str, sync_offset_ms: int = 0):
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.master_client_name = master_client_name
        self.master_client = master_client_name
        self.server = None
        self.notifier = None
        self.is_playing = False
        self.last_ping_offset = 0
        self.last_ping_time = None
        self.local_player_offset = 0
        self.current_rating_key = None
        self.current_title = None
        self.current_media_path = None
        self.master_client_id = None
        self.is_valid_media = False
        self.elastic_limit_ms = 2000
        self.log_callback = None
        self.last_seek_time = 0
        self.sync_offset_ms = sync_offset_ms

    def _log(self, level, msg):
        if level == "info":
            logger.info(msg)
        elif level == "error":
            logger.error(msg)
        elif level == "warning":
            logger.warning(msg)
            
        if self.log_callback:
            try:
                self.log_callback(level if level != "warning" else "info", msg)
            except Exception:
                pass

    def connect(self):
        try:
            self._log("info", f"Connexion au serveur Plex à {self.plex_url}")
            self.server = PlexServer(self.plex_url, self.plex_token)
            self._log("info", f"Connexion réussie : {self.server.friendlyName}")
        except Exception as e:
            self._log("error", f"Échec de connexion au serveur Plex : {e}")
            raise

    def start_websocket_listener(self):
        self._log("info", "Démarrage du listener WebSocket...")
        self.notifier = self.server.startAlertListener(self._on_plex_message)
        self._log("info", "Listener démarré.")

    def reconnect(self, plex_url: str, plex_token: str, master_client_name: str):
        self._log("info", "Reconnexion demandée avec de nouveaux paramètres...")
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.master_client_name = master_client_name
        self.master_client = master_client_name
        self.is_playing = False
        self.current_rating_key = None
        self.current_title = None
        self.current_media_path = None
        self.master_client_id = None
        
        if self.notifier:
            try:
                self.notifier.stop()
            except Exception:
                pass
            self.notifier = None
            
        self.server = None
        self.connect()
        self.start_websocket_listener()

    def _on_plex_message(self, message):
        try:
            msg_type = message.get('type')
            
            if msg_type == 'playing':
                play_sessions = message.get('PlaySessionStateNotification', [])
                
                if not self.master_client_id:
                    active_players = []
                    target_client = getattr(self, 'master_client', '').lower().replace('_', ' ')
                    
                    # Trier les sessions pour prioriser celles qui sont en cours de lecture ("playing")
                    # car si l'utilisateur a 2 onglets Firefox, on veut celui qui joue le film !
                    sorted_sessions = []
                    for session in self.server.sessions():
                        if session.player:
                            state = getattr(session.player, 'state', '').lower()
                            if state == 'playing':
                                sorted_sessions.insert(0, session)
                            else:
                                sorted_sessions.append(session)
                                
                    # 1. Essayer de trouver le client maître spécifique
                    for session in sorted_sessions:
                        if session.player:
                            title = session.player.title
                            ip_addr = getattr(session.player, 'address', '')
                            is_local_flag = getattr(session.player, 'local', False)
                            is_lan = is_local_flag or ip_addr.startswith('192.168.') or ip_addr.startswith('10.') or ip_addr.startswith('127.')
                            
                            active_players.append(f"{title} (LAN: {is_lan}, State: {getattr(session.player, 'state', '')})")
                            
                            if is_lan and session.type in ['movie', 'episode', 'clip']:
                                # Match flexible sur le nom
                                title_clean = title.lower().replace('_', ' ')
                                if target_client and target_client in title_clean:
                                    self.master_client_id = session.player.machineIdentifier
                                    self._log("info", f"Flux LOCAL accroché sur le lecteur désigné : {title} ({ip_addr})")
                                    break
                                elif not target_client:
                                    self.master_client_id = session.player.machineIdentifier
                                    self._log("info", f"Flux LOCAL accroché (par défaut) : {title} ({ip_addr})")
                                    break
                                    
                    # 2. Si non trouvé par nom, prendre le premier flux local
                    if not self.master_client_id and target_client:
                        for session in sorted_sessions:
                            if session.player:
                                ip_addr = getattr(session.player, 'address', '')
                                is_local_flag = getattr(session.player, 'local', False)
                                is_lan = is_local_flag or ip_addr.startswith('192.168.') or ip_addr.startswith('10.') or ip_addr.startswith('127.')
                                if is_lan and session.type in ['movie', 'episode', 'clip']:
                                    self.master_client_id = session.player.machineIdentifier
                                    self._log("info", f"Lecteur cible non trouvé, utilisation du premier lecteur LOCAL : {session.player.title}")
                                    break
                    
                    if not self.master_client_id:
                        if active_players:
                            self._log("info", f"En attente d'un flux vidéo en LOCAL... Lecteurs actifs : {', '.join(active_players)}")
                        return

                valid_session = None
                # Si l'utilisateur a deux onglets de lecture dans le même navigateur, 
                # ils partagent le même clientIdentifier. Il faut prioriser celui qui est en cours de lecture.
                for session_info in play_sessions:
                    if session_info.get('clientIdentifier') == self.master_client_id:
                        if session_info.get('state') == 'playing':
                            valid_session = session_info
                            break
                        elif not valid_session:
                            valid_session = session_info

                if not valid_session:
                    if self.is_playing and getattr(self, 'last_ping_time', None):
                        # Timeout de 15s si on ne reçoit plus de ping pour ce lecteur
                        if time.time() - self.last_ping_time > 15:
                            self._log("info", "Lecture arrêtée (timeout sans ping).")
                            self.is_playing = False
                            self.current_rating_key = None
                            self.current_media_path = None
                    return

                state = valid_session.get('state')
                if state == 'stopped':
                    if self.is_playing:
                        self._log("info", "Lecture arrêtée (signal stopped).")
                        self.is_playing = False
                    self.current_rating_key = None
                    self.current_media_path = None
                    return
                    
                view_offset = valid_session.get('viewOffset', 0)
                rating_key = valid_session.get('ratingKey')
                
                if rating_key and self.current_rating_key != rating_key:
                    self.current_rating_key = rating_key
                    self.is_valid_media = False
                    try:
                        item = self.server.fetchItem(int(rating_key))
                        if item.type in ['movie', 'episode', 'clip']:
                            self.is_valid_media = True
                            self.current_title = item.title
                            if hasattr(item, 'media') and item.media:
                                self.current_media_path = item.media[0].parts[0].file
                                
                                # Auto-détection du combo pour les presets
                                m = item.media[0]
                                res = m.videoResolution if hasattr(m, 'videoResolution') else 'unknown'
                                codec = m.videoCodec if hasattr(m, 'videoCodec') else 'unknown'
                                fps = m.videoFrameRate if hasattr(m, 'videoFrameRate') else 'unknown'
                                combo = f"{res}p-{codec}-{fps}fps".lower()
                                
                                if combo != getattr(self, 'current_combo', None):
                                    self.current_combo = combo
                                    if hasattr(self, 'combo_callback') and self.combo_callback:
                                        self.combo_callback(combo)
                                        
                            self._log("info", f"Lecture en cours : {self.current_title} ({self.current_media_path}) [Combo: {getattr(self, 'current_combo', 'unknown')}]")
                        else:
                            self._log("info", f"Média ignoré (type audio ou non supporté : {item.type})")
                    except Exception as e:
                        self._log("error", f"Erreur fetchItem: {e}")

                if not self.is_valid_media:
                    self.is_playing = False
                    return

                self.last_ping_offset = view_offset
                if state == 'playing':
                    self.last_ping_time = time.time()
                else:
                    self.last_ping_time = None

                # Logguer lors de la reprise de lecture pour que l'utilisateur le voie même après
                if state == 'playing' and not self.is_playing:
                    self._log("info", f"Reprise de la lecture : {self.current_title} ({self.current_media_path})")

                self.is_playing = (state == 'playing')

        except Exception as e:
            self._log("error", f"Erreur lors de l'analyse du message Plex: {e}")

    @property
    def current_view_offset(self):
        offset = getattr(self, 'sync_offset_ms', 0)
        if self.is_playing and getattr(self, 'last_ping_time', None):
            return self.last_ping_offset + int((time.time() - self.last_ping_time) * 1000) + offset
        return getattr(self, 'last_ping_offset', 0) + offset

    def compute_chase_speed(self, local_offset_ms: int):
        diff = self.current_view_offset - local_offset_ms
        
        if abs(diff) > self.elastic_limit_ms:
            now = time.time()
            if now - getattr(self, 'last_seek_time', 0) > 5.0:
                self.last_seek_time = now
                return None # Faut faire un seek
            else:
                return 1.0 # En cooldown, on laisse rouler à vitesse normale

        if abs(diff) < 100:
            return 1.0
        elif diff > 0:
            return 1.05
        else:
            return 0.95

    async def run(self):
        self.connect()
        self.start_websocket_listener()
        try:
            while True:
                if self.is_playing:
                    action = self.compute_chase_speed(self.local_player_offset)
                    self._log("info", f"Action recommandée pour MPV : {action if action else 'SEEK'}")
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self._log("info", "Arrêt demandé...")
            if self.notifier:
                self.notifier.stop()

if __name__ == "__main__":
    PLEX_URL = os.environ.get("PLEX_URL", "http://127.0.0.1:32400")
    PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "YOUR_TOKEN_HERE")
    MASTER_CLIENT = "Sony Bravia"
    sync = PlexSynchronizer(PLEX_URL, PLEX_TOKEN, MASTER_CLIENT)
    asyncio.run(sync.run())
