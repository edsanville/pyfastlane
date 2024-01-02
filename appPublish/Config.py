from dataclasses import dataclass


@dataclass
class AppConfig:
    workspace: str
    project: str
    scheme: str
    app_id: int
    bundle_id: str


@dataclass
class ConnectConfig:
    username: str
    team_name: str


@dataclass
class ScreenshotConfig:
    devices: str
    languages: str


@dataclass
class Config:
    app: AppConfig
    connect: ConnectConfig
    screenshots: ScreenshotConfig
