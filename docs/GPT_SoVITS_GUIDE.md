## 설치 및 가상 환경 설정
- **GPT-SoVITS** 세팅 과정에서 제가 문제를 해결한 방법을 요약하였습니다. **그러므로, 제 운영체제나 파이썬 버전과 다를 경우에는 다른 문제가 발생할 수 있습니다. 그런 경우에는 다른 GPT-SoVITS 설치 요령을 참고하세요.** 현재 제 운영체제는 Windows 11 Pro이며, 파이썬 버전은 Python 3.10.19입니다.
- GPT-SoVITS-v2가 업데이트 된 경우에는 변경될 수 있습니다. 현재 버전은 `20240821v2`입니다.
- 다운로드는 `https://github.com/RVC-Boss/GPT-SoVITS/releases`에서 `20240821v2`을 `windows 7z package download`를 받으시면 됩니다. 아래는 즉시 설치 가능한 링크입니다.
``` link
https://huggingface.co/lj1995/GPT-SoVITS-windows-package/resolve/main/GPT-SoVITS-v2-240821.7z
```
- **설치한 폴더는 기본 이름인 'GPT-SoVITS-v2-240821'을 그대로 사용하시고, 프로젝트의 assets 폴더에 넣어주세요.**
- GPT-SoVITS 권장과 같이, 아나콘다 설치 후, Anaconda PowerShell Prompt를 **관리자 권한으로 실행**하고 가상환경 만들고 활성화해야 합니다. 가상환경 이름은 제가 사용한 'GPTSoVITS_FINAL'을 사용하셔야 오류 없이 실행됩니다.
``` powershell
conda create -n GPTSoVITS_FINAL python=3.10 -y
```
## 라이브러리 설치
1. 충돌이 일어나기 쉬운 PyTorch, NumPy, Numba를 먼저 설치합니다. 저는 GPU 버전을 설치하였습니다. 참고로 제 GPU는 RTX4060 8GB입니다. 차이가 있는 경우에는 달라질 수 있습니다.
``` powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```
2. 그냥 설치하면 버전 오류가 발생하므로, `LangSegment`을 0.3.5버전으로 설치하여야 합니다. 그러나, 해당 라이브러리는 공식 저장소에 없기 때문에, huggingface에서 수동 설치하여야 합니다.
``` link
https://huggingface.co/ModelsLab/langsegment-whl/blob/main/langsegment-0.3.5-py3-none-any.whl
```
``` powershell
# 위 파일 포함 경로에서
pip install LangSegment-0.3.5-py3-none-any.whl
```
3. 실행에 `soxr`가 필요하므로, 미리 설치합니다.
``` powershell
pip install soxr
```
4. Gradio 라이브러리의 버전이 실행에 필요한 버전과 맞지 않으므로, 아래 버전으로 설치하여야 합니다.
``` powershell
pip install gradio==4.44.1
```
5. 이후에 나머지 의존성을 설치하세요. 이는 'GPT-SoVITS-v2-240821' 폴더에 포함되어 있습니다. 그전에, 위에서 이미 설치한 torchaudio, numpy, numba, LangSegment, gradio는 의존성 파일에서 주석 처리하셔야 합니다.
``` powershell
pip install -r requirements.txt
```
6. 이대로는 `Gradio`와 `Pydantic` 라이브러리 간의 버전 충돌(호환성 문제)이 발생합니다. 문제가 되는 라이브러리 버전을 강제로 고정합니다.
``` powershell
pip install pydantic==2.10.6
```
## 코드 수정
1. `GPT_SoVITS\TTS_infer_pack\TextPreprocessor.py`의 116~117번째 줄의 `segment_and_extract_feature_for_text`의 `return self.get_phones_and_bert(text, language, version)`을 `return self.get_phones_and_bert(text, language, 'v2')`으로 변경하여야 합니다.
3. 현재 상태로는 `NameError: name 'Tuple' is not defined. Did you mean: 'tuple'?`이 지속적으로 발생합니다.
   `.\GPT_SoVITS\AR\modules\patched_mha_with_cache.py`에서 코드 상단에, `from typing import Tuple, Optional`를 추가합니다.
## 테스트
- webui말고, 문제가 가장 자주 발생하는 GPT_SoVITS/inference_webui.py로 직접 테스트해야 합니다. GPT-SoVITS-v2-240821 폴더에서 아래 명령어로 쉽게 실행할 수 있습니다.
``` powershell
python GPT_SoVITS/inference_webui.py
```

- 아래와 같이 나오며, 정상적으로 추론을 위한 페이지가 실행되면 성공입니다.
``` powershell
(GPTSoVITS_FINAL) PS W:\GPT-SoVITS-v2-240821> python GPT_SoVITS/inference_webui.py

W:\conda\envs\GPTSoVITS_FINAL\lib\site-packages\librosa\util\files.py:10: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.

  from pkg_resources import resource_filename

<All keys matched successfully>

Number of parameter: 77.61M
```
## 마무리
- 이제 `README.md`와 같이, 학습된 모델 파일을 삽입하면 정상적으로 동작합니다. 저작권 관련 문제로 현재 프로젝트에 이용한 음성을 직접 제공하지 못하므로, `webui.py`로 직접 학습시켜서 사용하면 좋습니다.
