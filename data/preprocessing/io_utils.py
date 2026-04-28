"""전처리 결과 버전 관리 유틸리티.

저장 시 output/preprocessed/versions/ (또는 output/features/versions/) 에
타임스탬프 사본을 자동 생성한다.
"""

import os
import shutil
from datetime import datetime


def save_versioned(path: str) -> str | None:
    """파일을 저장한 뒤 versions/ 폴더에 타임스탬프 사본 보존.

    Returns:
        저장된 버전 파일 경로. 원본이 없으면 None.
    """
    if not os.path.exists(path):
        return None
    dir_ = os.path.dirname(path) or "."
    name, ext = os.path.splitext(os.path.basename(path))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    versions_dir = os.path.join(dir_, "versions")
    os.makedirs(versions_dir, exist_ok=True)
    dst = os.path.join(versions_dir, f"{name}_{ts}{ext}")
    shutil.copy2(path, dst)
    return dst
