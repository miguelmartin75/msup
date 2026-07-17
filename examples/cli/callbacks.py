def identity_step_fn(i: int, base_lr: float):
    return base_lr


def cosine_warmup_lr_step(i: int, base_lr: float):
    return base_lr
