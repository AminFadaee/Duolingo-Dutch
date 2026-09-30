from functools import cached_property

MODEL = "Helsinki-NLP/opus-mt-nl-en"
REVISION = "48af999f2c59b10c05ca6e008dcedc07677a9b15"
BATCH_SIZE = 16
BEAMS = 4


class Translator:
    name = f"{MODEL}@{REVISION[:12]}"

    @cached_property
    def model(self):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, revision=REVISION).eval()
        return tokenizer, model

    def translate(self, sentences: list[str]) -> list[str]:
        import torch

        tokenizer, model = self.model
        translations = []
        for start in range(0, len(sentences), BATCH_SIZE):
            batch = tokenizer(sentences[start:start + BATCH_SIZE], return_tensors="pt", padding=True)
            with torch.no_grad():
                output = model.generate(**batch, num_beams=BEAMS, do_sample=False, max_new_tokens=128)
            translations += tokenizer.batch_decode(output, skip_special_tokens=True)
        return translations
