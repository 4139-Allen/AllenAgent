"""
模型服务层

模型查询与切换。
"""


def list_models(model_manager):
    """列出所有可用模型"""
    from config import AppConfig
    from infrastructure.model_manager import ModelManager

    return {
        "models": [
            {
                "name": m.name,
                "model": m.model,
                "protocol": m.protocol,
                "is_current": m.model == model_manager.current_model,
            }
            for m in model_manager.config.available_models
        ],
        "current": model_manager.current_model,
    }


def switch_model(model_manager, model_name: str):
    """切换当前模型"""
    result = model_manager.switch(model_name)
    if "❌" in result:
        return {"status": "error", "message": result}
    return {
        "status": "ok",
        "message": result,
        "current_model": model_manager.current_model,
    }
