#!/usr/bin/env python3
"""
Configuration Manager

Handles loading and validation of configuration from config.env file.
Provides a centralized way to access configuration values with proper validation.
"""

import os
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Config:
    """Configuration container with validation"""
    
    # Master list method
    master_list_method: str
    transcript_method: str
    
    # API keys
    youtube_api_key: Optional[str]
    
    # File paths
    master_file: str
    channel_url: str
    
    # Update settings
    max_videos_per_update: int
    update_frequency: str
    
    # yt-dlp configuration
    ytdlp_cookies_file: Optional[str]
    ytdlp_use_proxy: bool
    
    # Proxy configuration
    webshare_proxy_username: Optional[str]
    webshare_proxy_password: Optional[str]
    webshare_proxy: Optional[str]
    
    # Notification settings
    discord_webhook_url: Optional[str]
    email_notifications: bool
    
    # Categories
    default_categories: list

class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_file: str = "config.env"):
        self.config_file = config_file
        self.config = None
    
    def load_config(self) -> Config:
        """Load configuration from file with validation"""
        if self.config:
            return self.config
            
        logger.info(f"Loading configuration from {self.config_file}")
        
        # Load environment variables from file
        env_vars = self._load_env_file()
        
        # Validate required configurations
        self._validate_config(env_vars)
        
        # Create config object
        self.config = Config(
            master_list_method=env_vars.get('MASTER_LIST_METHOD', 'youtube_api'),
            transcript_method=env_vars.get('TRANSCRIPT_METHOD', 'ytdlp'),
            youtube_api_key=env_vars.get('YOUTUBE_API_KEY'),
            master_file=env_vars.get('MASTER_FILE', 'data/videos_master.json'),
            channel_url=env_vars.get('CHANNEL_URL', 'https://www.youtube.com/@AdamSeekerOfficial'),
            max_videos_per_update=int(env_vars.get('MAX_VIDEOS_PER_UPDATE', '50')),
            update_frequency=env_vars.get('UPDATE_FREQUENCY', 'daily'),
            ytdlp_cookies_file=env_vars.get('YTDLP_COOKIES_FILE'),
            ytdlp_use_proxy=env_vars.get('YTDLP_USE_PROXY', 'false').lower() == 'true',
            webshare_proxy_username=env_vars.get('WEBSHARE_PROXY_USERNAME'),
            webshare_proxy_password=env_vars.get('WEBSHARE_PROXY_PASSWORD'),
            webshare_proxy=env_vars.get('WEBSHARE_PROXY'),
            discord_webhook_url=env_vars.get('DISCORD_WEBHOOK_URL'),
            email_notifications=env_vars.get('EMAIL_NOTIFICATIONS', 'false').lower() == 'true',
            default_categories=env_vars.get('DEFAULT_CATEGORIES', 'critique-of-islam,theology,apologetics,debate').split(',')
        )
        
        logger.info("Configuration loaded successfully")
        return self.config
    
    def _load_env_file(self) -> Dict[str, str]:
        """Load environment variables from config file"""
        env_vars = {}
        
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        return env_vars
    
    def _validate_config(self, env_vars: Dict[str, str]) -> None:
        """Validate configuration values"""
        # Validate master list method
        master_method = env_vars.get('MASTER_LIST_METHOD', 'youtube_api')
        if master_method not in ['youtube_api', 'ytdlp']:
            raise ValueError(f"Invalid MASTER_LIST_METHOD: {master_method}. Must be 'youtube_api' or 'ytdlp'")
        
        # Validate transcript method
        transcript_method = env_vars.get('TRANSCRIPT_METHOD', 'ytdlp')
        if transcript_method not in ['ytdlp', 'youtube_transcript_api']:
            raise ValueError(f"Invalid TRANSCRIPT_METHOD: {transcript_method}. Must be 'ytdlp' or 'youtube_transcript_api'")
        
        # Validate API key requirement
        if master_method == 'youtube_api' and not env_vars.get('YOUTUBE_API_KEY'):
            raise ValueError("YOUTUBE_API_KEY is required when MASTER_LIST_METHOD=youtube_api")
        
        # Validate file paths
        master_file = env_vars.get('MASTER_FILE', 'data/videos_master.json')
        if not master_file:
            raise ValueError("MASTER_FILE cannot be empty")
        
        # Validate channel URL
        channel_url = env_vars.get('CHANNEL_URL', 'https://www.youtube.com/@AdamSeekerOfficial')
        if not channel_url or not channel_url.startswith('https://www.youtube.com/'):
            raise ValueError("CHANNEL_URL must be a valid YouTube channel URL")
        
        # Validate cookies file if specified
        cookies_file = env_vars.get('YTDLP_COOKIES_FILE')
        if cookies_file and not os.path.exists(cookies_file):
            logger.warning(f"Cookies file specified but not found: {cookies_file}")
        
        # Validate proxy configuration
        proxy_username = env_vars.get('WEBSHARE_PROXY_USERNAME')
        proxy_password = env_vars.get('WEBSHARE_PROXY_PASSWORD')
        proxy = env_vars.get('WEBSHARE_PROXY')
        
        if proxy and not proxy.startswith('http://'):
            raise ValueError("WEBSHARE_PROXY must start with 'http://'")
        
        if (proxy_username or proxy_password) and not (proxy_username and proxy_password):
            raise ValueError("Both WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD must be provided together")
        
        logger.info("Configuration validation passed")
    
    def get_master_fetcher_config(self) -> Dict[str, Any]:
        """Get configuration for master list fetching"""
        config = self.load_config()
        
        fetcher_config = {
            'method': config.master_list_method,
            'channel_url': config.channel_url,
            'max_videos': config.max_videos_per_update
        }
        
        if config.master_list_method == 'youtube_api':
            if not config.youtube_api_key:
                raise ValueError("YOUTUBE_API_KEY is required for youtube_api method")
            fetcher_config['api_key'] = config.youtube_api_key
        
        elif config.master_list_method == 'ytdlp':
            fetcher_config['cookies_file'] = config.ytdlp_cookies_file
            fetcher_config['use_proxy'] = config.ytdlp_use_proxy
            if config.ytdlp_use_proxy:
                if config.webshare_proxy:
                    fetcher_config['proxy'] = config.webshare_proxy
                elif config.webshare_proxy_username and config.webshare_proxy_password:
                    fetcher_config['proxy'] = f"http://{config.webshare_proxy_username}:{config.webshare_proxy_password}@proxy.webshare.io:80"
        
        return fetcher_config
    
    def get_transcript_downloader_config(self) -> Dict[str, Any]:
        """Get configuration for transcript downloading"""
        config = self.load_config()
        
        downloader_config = {
            'method': config.transcript_method
        }
        
        if config.transcript_method == 'ytdlp':
            downloader_config['cookies_file'] = config.ytdlp_cookies_file
            downloader_config['use_proxy'] = config.ytdlp_use_proxy
            if config.ytdlp_use_proxy:
                if config.webshare_proxy:
                    downloader_config['proxy'] = config.webshare_proxy
                elif config.webshare_proxy_username and config.webshare_proxy_password:
                    downloader_config['proxy'] = f"http://{config.webshare_proxy_username}:{config.webshare_proxy_password}@proxy.webshare.io:80"
        
        elif config.transcript_method == 'youtube_transcript_api':
            if config.webshare_proxy:
                downloader_config['proxy'] = config.webshare_proxy
            elif config.webshare_proxy_username and config.webshare_proxy_password:
                downloader_config['proxy_username'] = config.webshare_proxy_username
                downloader_config['proxy_password'] = config.webshare_proxy_password
        
        return downloader_config

# Global config manager instance
config_manager = ConfigManager()