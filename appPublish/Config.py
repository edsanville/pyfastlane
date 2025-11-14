from dataclasses import dataclass


@dataclass
class AppConfig:
    workspace: str
    project: str
    scheme: str
    app_id: int
    bundle_id: str
    uses_encryption: bool = False
    uses_idfa: bool = False


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
