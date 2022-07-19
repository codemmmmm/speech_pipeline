from transformers import MarianMTModel, MarianTokenizer

#https://huggingface.co/Helsinki-NLP/opus-mt-en-de
#https://huggingface.co/Helsinki-NLP/opus-mt-de-en
model_name = "Helsinki-NLP/opus-mt-en-de"
model = MarianMTModel.from_pretrained(model_name)
tokenizer = MarianTokenizer.from_pretrained(model_name)
directory = 'translate-en-de'
tokenizer.save_pretrained(directory)
model.save_pretrained(directory)


