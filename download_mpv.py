import os
import requests
import py7zr
import re
import sys

def download_and_extract_mpv():
    print("Recherche de la dernière version de libmpv pour Windows...")
    api_url = "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        # Trouver l'asset qui contient 'mpv-dev-x86_64'
        download_url = None
        file_name = None
        for asset in data.get("assets", []):
            if "mpv-dev-x86_64" in asset.get("name", "") and asset.get("name", "").endswith(".7z"):
                download_url = asset.get("browser_download_url")
                file_name = asset.get("name")
                break
                
        if not download_url:
            print("Erreur: Impossible de trouver mpv-dev-x86_64 dans la dernière release.")
            sys.exit(1)
            
        print(f"Téléchargement de {file_name}...")
        archive_path = os.path.join(os.getcwd(), file_name)
        
        # Téléchargement
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(archive_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        print(f"Extraction de mpv-2.dll depuis {file_name}...")
        # Extraction du dll
        found_dll = False
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            all_files = z.getnames()
            dll_files = [f for f in all_files if f.endswith('.dll') and 'mpv' in f]
            
            if not dll_files:
                print("Erreur: Aucun fichier DLL mpv trouvé. Voici le contenu :")
                for f in all_files:
                    print(" -", f)
            else:
                dll_name = dll_files[0]
                print(f"Fichier trouvé : {dll_name}")
                z.extract(targets=[dll_name], path=os.getcwd())
                
                # Si le fichier est dans un sous-dossier ou s'appelle libmpv-2.dll, on le met au bon format à la racine
                extracted_path = os.path.join(os.getcwd(), dll_name)
                final_path = os.path.join(os.getcwd(), 'mpv-2.dll')
                
                if extracted_path != final_path:
                    # Move to root if needed
                    basename = os.path.basename(extracted_path)
                    os.rename(extracted_path, os.path.join(os.getcwd(), basename))
                    if basename != 'mpv-2.dll':
                        os.rename(os.path.join(os.getcwd(), basename), final_path)
                
                found_dll = True
                
        # Nettoyage
        print(f"Suppression de l'archive {archive_path}...")
        os.remove(archive_path)
        
        if found_dll:
            print("Opération réussie ! Le DLL mpv est prêt.")
        else:
            sys.exit(1)
            
    except Exception as e:
        print(f"Une erreur s'est produite : {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_and_extract_mpv()
