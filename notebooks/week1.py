import sys
from pathlib import Path
import subprocess
import json 
import asyncio
import requests
import time
import socket
import psycopg2

async def check_python_version():
    python_version=sys.version_info
    print(f"Python version:{python_version.major}.{python_version.minor}.{python_version.micro}")
    print(f"Environment:{sys.executable}")

    if python_version>=(3,12):
        print("Python version compatable")
    else:
        print("Python version not compatable, since python version < 3.12")

current_dir = Path(__file__).resolve().parent

async def check_project_directory():
    if current_dir.name == "notebooks":
        project_dir = current_dir.parent

    elif (current_dir / "compose.yml").exists():
        project_dir = current_dir

    else:
        project_dir = None

    if project_dir and (project_dir / "compose.yml").exists():
        print(f"Project root: {project_dir}")
    else:
        print("Project root not found or is not at the right directory")
        exit()

async def check_docker_version():
    try:
        result=subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout = 5)
        if result.returncode==0:
            print(f"Docker working: {result.stdout}")
        else:
            print(f"Docker not working: {result.stderr}")
            exit()
    except:
        print("Docker not found")
        exit()

async def check_docker_compose_version():
    try:
        result=subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=5)
        if result.returncode==0:
            print(f"Docker compose working: {result.stdout.split()[3]}")
        else:
            print(f"Docker compose is not working {result.stderr}")
            exit()
    except:
        print("Docker compose not found")
        exit()

async def check_uv_version():
    try:
        result=subprocess.run(["uv","--version"], capture_output=True, text=True, timeout=5)
        if result.returncode==0:
            print(f"UV working: {result.stdout.strip()}")
        else:
            print(f"UV is not working {result.stderr}")
            exit()
    except:
        print("UV is not found")
        exit()

# try:
#     subprocess.run(["Docker", "compose", "up"," -d"], capture_output=True, text=True, timeout=5)
# except Exception as e: 
#     print(f"Docker compose error: {e}")

async def get_running_docker_compose_container():
    try:
        result=subprocess.run(["docker","compose", "ps", "--format", "json"], 
                            cwd=project_dir,
                            capture_output=True, 
                            text=True, 
                            timeout=5)
        print(result)
        if result.returncode!=0:
            print(f"Could not check containers: {result.stderr}")
        elif not result.stdout.strip():
            print("No container running")
        else:
            for line in result.stdout.strip().splitlines():
                    try:
                        container=json.load(line)
                        service=container.get("Service", "unknown")
                        state=container.get("State","unknown")
                        print(f" - {service}:{state}")
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print("Could not check containers")


# CHECK IF THE EXPECTED SERVICES ARE RUNNING OR NOT 

EXPECTED_SERVICES = {
    "api":"FastAPI REST API services",
    "postgres":"Postgres Database Service",
    "opensearch":"OpenSearch search engine",
    "opensearch-dashboard":"Opensearch search engine dashboard",
    "ollama":"Local LLM inference server",
    "airflow":"Workflow automation (maybe-turned off)"
}

found_services=set()
service_status={}
async def find_running_containers():
    try:
        result=subprocess.run(["docker","compose","ps","--format","json"], 
                            cwd=project_dir,
                            capture_output=True,
                            text=True,
                            timeout=5)
        if result.returncode==200:
            if result.stdout.strip:
                for line in result.stdout.strip().strip('\n'):
                    if line.strip():
                        container=json.loads(line)
                        service=container.get("service","unknown")
                        state=container.get("state","unknown")
                        health=container.get("health","unknown")

                        found_services.add(service)
                        service_status[service]={"state":state,
                                                "health":health}
        else:
                    print("Could not get service status")

        return found_services, service_status

    except Exception as e:
        print(f"Error checking service: {e}")

async def missing_services(found_services:set):
    failed_services=[]
    missing_services=EXPECTED_SERVICES-found_services
    try:
        if missing_services:
            for each_service in service_status:
                if each_service.each_state in ["exited", "restarting"] and each_service.each_health in ["unhealthy"]:
                    failed_services.append(each_service.key)
        return failed_services

    except Exception as e:
        print(f"Error occured finding missing service: {e}")

    try:
        if failed_services:
            print(f"The Failed services are:{failed_services}")
            for each_failed_service in failed_services:
                log_of_each_service=subprocess.run(["docker","compose","logs",each_failed_service],
                                                    timeout=10,
                                                    cwd=project_dir,
                                                    capture_output=True,
                                                    text=True)
                if result.returncode==200:
                    print(f"Logs of {each_failed_service} is : {result.stdout}")
                else:
                    print(f"Couldnt retrieve logs for the failed service: {each_failed_service}")

    except Exception as e:
            print(f"Error occued during retrieving logs of failed service: {e}")

async def test_api_container():
    try:
        response=requests.get("http://localhost:8000/v1/api/health", timeout=5)
        if response:
            if response.status_code==200:
                data=response.json()
                print("Fastapi container response:")
                print(f"Status:{data.get("status", "unknown")}")
            else:
                print(f"API return status:{response.status_code}")

    except requests.exceptions.ConnectionError:
        print("API connection error, try in 1-2 minutes")
    except Exception as e:
        print(f"Error testing the api container: {e}")

password_path=project_dir/"airflow"/"simple_auth_manager_passwords.json.generated"

async def test_airflow_container():
    try: 
        if password_path.exists():
            with open(password_path, "w") as f:
                data=json.load(f)
                password=data.get("admin")
                print(f"The airflow password is : {password}")
        else:
            print("Could not find password file")
            password=None
    except Exception as e:
        print(f"Could not find passwords file {e}")
        password=None

    try:
        response=requests.get(url="http://localhost:8080/api/v1/health", timeout=5)
        if response.status_code==200:
            print("Airflow container is healthy")

            if password:
                print("Airflow login URL and credentials:")
                print("URL: http:localhost:8080")
                print("Username: admin")
                print(f"Passwords: {password}")

        else:
            print(f"Request error: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("Connection error with airflow container please try in 2-3 minutes")

    except Exception as e:
        print(f"Error occured: {e}")

opensearch_dashboard_url="http://localhost:5601"

"""
    
"""
async def test_opensearch_container():
    try:
        response=requests.get(url=opensearch_dashboard_url, timeout=10, allow_redirects=True)
        if response.status_code==200:
            print("Opensearch dashboard is accessible")
            print("✓ Web interface is ready for exploration")
        
            print("\n Web Interface Access:")
            print("=" * 40)
            print(f"Main Dashboard: {opensearch_dashboard_url}")
            print(f"Dev Tools: {opensearch_dashboard_url}/app/dev_tools")
            print("=" * 40)
            
            print("\n Student Learning Activities:")
            print("1. Explore the Dashboard:")
            print("   • Visit http://localhost:5601")
            print("   • Navigate through the interface")
            print("   • Check out the 'Discover' tab")
            
            print("\n2. Use Dev Tools for API Queries:")
            print("   • Go to Dev Tools")
            print("   • Try: GET /_cluster/health")
            print("   • Try: GET /_cat/indices?v")
            print("   • Try: GET /_cluster/stats")
            print("   • Check the learning material for more information")
        else:
            print(f"⚠ Dashboards returned status: {response.status_code}")
            print("Interface may still be starting up")


    except requests.exceptions.Timeout:
        print("Opensearch dashboard request timedout")
        print("This is normal during startup. Try again in a few minutes")

    except requests.exceptions.ConnectionError:
        print("Opensearch dashboard not accesssible yet. This is usual at the start of the container")
        print("Try again in 2-3 minutes")

    except Exception as e:
        print(f"Error occured at getting a response from the opensearch dashboard container: {e}")
        print("Try checking the logs of the container : docker logs container_name")

ollama_container_url="http://localhost:11434"

async def test_ollama_container():
    try:
        model_version=requests.get(url=f"{ollama_container_url}/api/tags", timeout=10)
        if model_version.status_codes==200:
            json_response=model_version.json()
            available_models=model_version.get("model", [])
            print("Ollama available models")
            print(f"The number of available models are: {len(available_models)}")

            if available_models:
                for each_model in available_models:
                    name_of_each_model=each_model.get("name", "unknown")
                    size_of_each_model=each_model.get("size", 0)
                    size_in_gb=round(size_of_each_model/1024*3, 1)
                    print(f"{name_of_each_model}:{size_in_gb}")
            else:
                print("No models installed yet")
                print("This is normal. Since models are larger files (3-7 GB)")
                print("In week 4 we will install model like llama 3.2")

            print("Try this again ")

    except requests.exceptions.Timeout:
        print("Ollama container request timed out")
        print("This normal at the start of the container. Try again in a few minutes")

    except requests.exceptions.ConnectionError:
        print("Ollama container not responding")
        print("Ollama service might still be starting try again in a few minutes")
    except Exception as e:
        print(f"Unexcpected error testing ollama: {e}")
        print("Try again in a few minutes")

    try:
        response=requests.get(url=f"{ollama_container_url}/api/version", timeout=10)
        if response.status_code==200:
            json_response=response.json()
            ollama_version=json_response.get("version", "unknown")
            print("Ollama api is healthy")
            print(f"Ollama version is: {ollama_version}")

            print("\n  What is Ollama?")
            print("• Runs AI models completely on your local machine")
            print("• No data sent to external services (privacy-first)")
            print("• No API fees or rate limits")
            print("• Supports models like Llama, Mistral, Phi, etc.")
            
            print("\n  Coming in Week 4:")
            print("• Install and run a local language model")
            print("• Generate answers to research questions")
            print("• Summarize academic papers")
            print("• All processing stays on your computer!")

        else:
            print(f"Ollama version check returned: {response.status_code}")

    except requests.exceptions.Timeout:
        print("Ollama api response timedout")
        print("This is normal at the start of the container. Try again in a few minutes")

    except requests.exceptions.ConnectionError:
        print("Ollama api connection error")
        print("Service might still be initiallizing. Try again in a few minutes")

    except Exception as e:
        print(f"Unexpected error checking version: {e}")
        print("Try again in a few minutes")

async def pull_ollama_llm():
    try:
        result=subprocess.run(args=["docker","exec", "rag-ollama", "pull", "ollama3.2:1b"],
                       cwd=project_dir,
                       timeout=60,
                       text=True,
                       capture_output=True)
        if result.returncode==200:
            print("Success! Ollama3.2:1b has been successfully pulled")
        else:
            print(f"Download issue: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("Download timedout - This is normal for slow internet connection")
        print("Don't worry the download continues in the background")

    except Exception as e:
        print(f"Error downloading model: {e}")
        print("Make sure the rag-ollama container is running: docker compose ps")

async def test_ollama_llm_with_prompt(model_name, prompt, max_wait_timeout=60):
    ollama_llm_api="http://localhost:11434/api/generate"
    print(f"Testing {model_name} with prompt: {prompt}")

    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    try:
        print("Generating response. This may take 10-30 seconds")
        response=requests.post(url=ollama_llm_api, json=data ,timeout=max_wait_timeout) 
        start_time=time.time()

        if response.status_code==200:
            response_text=response.get("response", " ").strip()
            ellapsed_time = start_time - time.time()
            print(f"Response time: {ellapsed_time}")
            print("\nResponse")
            print('='*40)
            print(response_text)

            if 'model' in response_text:
                model_name=response_text.get("model", "unknown")
                print(f"Model:"{model_name})

            if 'total_duration' in response_text:
                total_duration=response_text.get("total_duration", "unknown")
                total_duration_in_minutes=total_duration/1000000
                print(f"Total duration: {total_duration}")

            return True

        else:
            print(f"API error:{response.status_code}")
            print(f"Response text: {response.text}")

    except requests.exceptions.ConnectionError:
        print("Ollama Connection error : Could not connect to Ollama API")
        print("Make sure the ollama docker container is running: docker compose ps ")
        return False
    except requests.exceptions.Timeout:
        print("Ollama Timeout error")
        print("Model might be loading for the first time (this is normal)")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
test_prompt = "What is machine learning in one sentence?"
success=test_ollama_llm_with_prompt(model_name="ollama3.2:1b",prompt=test_prompt)

if success:
    print("\nSUCCESS! Your local AI model is working!")
    print("\nTry more prompts:")
    print('• test_ollama_model("llama3.2:1b", "Explain neural networks simply")')
    print('• test_ollama_model("llama3.2:1b", "Write a Python function to sort a list")')
else:
    print("\nTroubleshooting:")
    print("1. Make sure model downloaded: docker exec rag-ollama ollama list")
    print("2. Check Ollama logs: docker compose logs ollama")
    print("3. Try again - first run takes longer to load model into memory")


async def test_postgresql_socket_connection():
    try:
        sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        response=sock.connect_ex(("localhost",5432))
        sock.close

        if response==0:
            print("PostgreSQL is accepting connection at port 5432")
            return True

        else:
            print("Postgresql port 5432 is not accessible")

    except Exception as e:
        print(f"Error occured testing socker connection with postgresql port 5432: {e}")

async def test_postgresql_db_connection():
    try: 
        conn=psycopg2.connect(
            host="localhost",
            port=5432,
            database="rag_db",
            user='rag_user',
            password='password'
        )
        print("Postgresql connection established")
        cursor=conn.cursor()

    except Exception as e:
        print(f"Postgresql Error occured trying to create connection: {e}")

    try:
        cursor.execute(query="""
                                SELECT table_name
                                FROM information_schema.tables
                                WHERE table_schema='public'
                                ORDERBY table_name;
""")
        all_tables=cursor.fetchall()
        app_tables=[]
        airflow_tables=[]
        for (table_name,) in all_tables:
            if table_name in ['papers', 'users', 'embeddings']:
                app_tables.append(table_name)
            else:
                airflow_tables.append(table_name)

        print(f"Found {len(all_tables)} of all tables")
        print(f"Length of Application tables: {len(app_tables)}")
        print(f"Lenght of Airflow tables" {len(airflow_tables)})

        for table in app_tables:
            print(f" - {table}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error occured executing the query: {e}")

    