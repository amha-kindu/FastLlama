.PHONY: start
start:
	# You need to set OPENAPI_API_KEY environment
	PYTHONPATH=. python app/launch.py

.PHONY: clean
clean:
	rm ./app/llama_index_server/saved_index/* | rm ./app/llama_index_server/pkl/*.pkl
