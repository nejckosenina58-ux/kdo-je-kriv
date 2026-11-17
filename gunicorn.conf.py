"""Nastavitve za gunicorn (Render). Ustvarjanje novega primera z AI lahko traja do ~2 minuti."""
timeout = 240
workers = 1      # igre so shranjene v pomnilniku, zato mora biti en proces
threads = 8      # več igralcev hkrati
