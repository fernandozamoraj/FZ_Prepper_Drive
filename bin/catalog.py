"""catalog.py (offline prepper kit v1.16.0): the optional modules: books, audiobooks, movies and software.

None of this is part of `install all`. Pick what you want:
    kit books                       menu: choose categories or type keywords
    kit books list [words]          what's available (and what you already have)
    kit books get WORDS [--audio]   e.g. books get math nursing dracula   (see README "Books, audiobooks, software")
    kit software get WORDS [--os windows,mac,linux]
    kit movies get WORDS            e.g. movies get comedy "night of the living dead"
    kit movies add https://archive.org/details/<id>   any other free film (or drop video files in movies/my-movies/)

To add a book, add a line to BOOKS: an id (one word, used on the command line), title, author, category, keywords,
and where it comes from (one of):
    openstax="slug"      newest live edition from OpenStax (PDF; OpenStax has no EPUB)
    gutenberg=NUMBER     Project Gutenberg EPUB (from a Gutenberg mirror, as Gutenberg asks for scripts)
    files={"epub": URL, "pdf": URL}   fixed download links
    pdf_index=(page, regex)           every PDF linked from a page (books published one chapter per file);
                                      regex groups: (chapter number or empty, file, title)
    zim=(folder, prefix)              a Kiwix library on download.kiwix.org (it shows up in the Library)
and optionally librivox="archive.org identifier" for a LibriVox audiobook (public domain MP3s).
Kept in bin/ because both scripts/kit.py (downloads) and bin/intranet.py (the Books and Software pages) use it.
"""
import os
import re

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_DIR, AUDIO_DIR, SOFTWARE_DIR, MOVIES_DIR = (os.path.join(KIT, d) for d in ("books", "audiobooks", "software", "movies"))

# category id: (name, group). A group name on the command line means all its categories.
CATEGORIES = {
    "math": ("Math", "textbooks"),
    "nursing": ("Nursing", "textbooks"),
    "science": ("Science", "textbooks"),
    "programming": ("Programming", "textbooks"),
    "business": ("Business", "textbooks"),
    "history": ("History and society", "textbooks"),
    "adventure": ("Fiction: adventure", "fiction"),
    "romance": ("Fiction: romance", "fiction"),
    "mystery": ("Fiction: mystery", "fiction"),
    "scifi": ("Fiction: science fiction and horror", "fiction"),
}
GROUPS = sorted({g for _, g in CATEGORIES.values()})

OX_LICENSE = "OpenStax, CC BY-NC-SA 4.0 (free to share unchanged with attribution; not for sale)"
PD = "Public domain in the USA (Project Gutenberg)"


def ox(id, title, cat, slug, kw=""):
    return dict(id=id, title=title, author="OpenStax", cat=cat, kw=kw, openstax=slug, license=OX_LICENSE)


def pg(id, title, author, cat, number, librivox=None, kw=""):
    return dict(id=id, title=title, author=author, cat=cat, kw=kw, gutenberg=number, librivox=librivox, license=PD)


BOOKS = [
    # ---- Math (OpenStax) ----
    ox("prealgebra", "Prealgebra", "math", "prealgebra", "arithmetic fractions decimals"),
    ox("elementary-algebra", "Elementary Algebra", "math", "elementary-algebra", "algebra equations"),
    ox("intermediate-algebra", "Intermediate Algebra", "math", "intermediate-algebra", "algebra"),
    ox("college-algebra", "College Algebra", "math", "college-algebra", "algebra functions"),
    ox("precalculus", "Precalculus", "math", "precalculus", "trigonometry functions"),
    ox("calculus-1", "Calculus Volume 1", "math", "calculus-volume-1", "calculus derivatives limits"),
    ox("calculus-2", "Calculus Volume 2", "math", "calculus-volume-2", "calculus integrals series"),
    ox("calculus-3", "Calculus Volume 3", "math", "calculus-volume-3", "calculus multivariable vectors"),
    ox("statistics", "Introductory Statistics", "math", "introductory-statistics", "statistics probability"),
    ox("contemporary-math", "Contemporary Mathematics", "math", "contemporary-mathematics", "math finance logic"),
    # ---- Nursing (OpenStax) ----
    ox("fundamentals-nursing", "Fundamentals of Nursing", "nursing", "fundamentals-nursing", "nurse medical care"),
    ox("pharmacology", "Pharmacology for Nurses", "nursing", "pharmacology", "drugs medicine nurse medical"),
    ox("maternal-newborn", "Maternal-Newborn Nursing", "nursing", "maternal-newborn-nursing",
       "pregnancy birth baby midwife nurse medical"),
    ox("psychiatric-nursing", "Psychiatric-Mental Health Nursing", "nursing", "psychiatric-mental-health",
       "mental health psychology nurse medical"),
    ox("nutrition", "Nutrition for Nurses", "nursing", "nutrition", "food diet nurse medical"),
    # ---- Science (OpenStax) ----
    ox("biology", "Biology", "science", "biology", "life cells genetics"),
    ox("chemistry", "Chemistry", "science", "chemistry", "chemicals atoms"),
    ox("college-physics", "College Physics", "science", "college-physics", "physics"),
    ox("university-physics-1", "University Physics Volume 1", "science", "university-physics-volume-1",
       "physics mechanics"),
    ox("university-physics-2", "University Physics Volume 2", "science", "university-physics-volume-2",
       "physics electricity magnetism"),
    ox("university-physics-3", "University Physics Volume 3", "science", "university-physics-volume-3",
       "physics optics modern"),
    # ---- Programming ----
    ox("intro-python", "Introduction to Python Programming", "programming", "introduction-python-programming",
       "python coding"),
    dict(id="think-python", title="Think Python (2nd edition)", author="Allen B. Downey", cat="programming",
         kw="python coding", files={"pdf": "https://greenteapress.com/thinkpython2/thinkpython2.pdf"},
         license="Green Tea Press, CC BY-NC 3.0"),
    dict(id="think-java", title="Think Java (2nd edition)", author="Allen B. Downey and Chris Mayfield",
         cat="programming", kw="java coding", files={"pdf": "https://greenteapress.com/thinkjava7/thinkjava2.pdf"},
         license="Green Tea Press, CC BY-NC-SA 3.0"),
    dict(id="open-data-structures", title="Open Data Structures (Python edition)", author="Pat Morin",
         cat="programming", kw="algorithms data structures python",
         files={"pdf": "https://opendatastructures.org/ods-python.pdf"}, license="CC BY 2.5"),
    dict(id="open-data-structures-java", title="Open Data Structures (Java edition)", author="Pat Morin",
         cat="programming", kw="algorithms data structures java",
         files={"pdf": "https://opendatastructures.org/ods-java.pdf"}, license="CC BY 2.5"),
    dict(id="ostep", title="Operating Systems: Three Easy Pieces", author="Remzi and Andrea Arpaci-Dusseau",
         cat="programming", kw="operating systems os unix",
         pdf_index=("https://pages.cs.wisc.edu/~remzi/OSTEP/",
                    r'(?:<small>(\d+)</small>\s*)?<a href="?([a-z0-9-]+\.pdf)"?[^>]*>([^<]+)</a>'),
         license="Free to read from the authors' site (their copyright: personal use, don't resell)"),
    dict(id="sicp", title="Structure and Interpretation of Computer Programs", author="Abelson, Sussman and Sussman",
         cat="programming", kw="scheme lisp sicp",
         files={"epub": "https://github.com/sarabander/sicp-epub/raw/master/sicp.epub",
                "pdf": "https://github.com/sarabander/sicp-pdf/raw/master/sicp.pdf"},
         license="CC BY-SA 4.0 (MIT Press text; edition by Andres Raba)"),
    dict(id="pro-git", title="Pro Git", author="Scott Chacon and Ben Straub", cat="programming", kw="git version control",
         files={"epub": "https://github.com/progit/progit2/releases/latest/download/progit.epub",
                "pdf": "https://github.com/progit/progit2/releases/latest/download/progit.pdf"},
         license="CC BY-NC-SA 3.0"),
    dict(id="rust-book", title="The Rust Programming Language (with the Rust docs)", author="Rust project",
         cat="programming", kw="rust coding", zim=("devdocs", "devdocs_en_rust_"),
         license="MIT / Apache-2.0 (Kiwix DevDocs library: opens in the Library)"),
    # ---- Business (OpenStax) ----
    ox("economics", "Principles of Economics", "business", "principles-economics", "economy markets money"),
    ox("management", "Principles of Management", "business", "principles-management", "management leadership"),
    ox("finance", "Principles of Finance", "business", "principles-finance", "finance money investing"),
    ox("financial-accounting", "Principles of Financial Accounting", "business", "principles-financial-accounting",
       "accounting bookkeeping"),
    ox("entrepreneurship", "Entrepreneurship", "business", "entrepreneurship", "startup small business"),
    ox("business-ethics", "Business Ethics", "business", "business-ethics", "ethics"),
    ox("business-law", "Business Law I Essentials", "business", "business-law-i-essentials", "law legal contracts"),
    # ---- History and society (OpenStax) ----
    ox("us-history", "U.S. History", "history", "us-history", "america united states"),
    ox("world-history-1", "World History Volume 1", "history", "world-history-volume-1", "ancient history"),
    ox("world-history-2", "World History Volume 2", "history", "world-history-volume-2", "modern history"),
    ox("philosophy", "Introduction to Philosophy", "history", "introduction-philosophy", "philosophy ethics logic"),
    ox("american-government", "American Government", "history", "american-government",
       "government politics constitution civics"),
    ox("anthropology", "Introduction to Anthropology", "history", "introduction-anthropology", "culture people"),
    # ---- Fiction (Project Gutenberg EPUB + LibriVox audiobook) ----
    pg("monte-cristo", "The Count of Monte Cristo", "Alexandre Dumas", "adventure", 1184, "count_monte_cristo_0711_librivox"),
    pg("three-musketeers", "The Three Musketeers", "Alexandre Dumas", "adventure", 1257, "three_musketeers_0712_librivox"),
    pg("treasure-island", "Treasure Island", "Robert Louis Stevenson", "adventure", 120, "treasureisland_librivox",
       "pirates"),
    pg("robinson-crusoe", "Robinson Crusoe", "Daniel Defoe", "adventure", 521, "robinson_crusoe_librivox",
       "island survival"),
    pg("lost-world", "The Lost World", "Arthur Conan Doyle", "adventure", 139, "lost_world_librivox", "dinosaurs"),
    pg("king-solomons-mines", "King Solomon's Mines", "H. Rider Haggard", "adventure", 2166, "king_solomon_librivox"),
    pg("pride-and-prejudice", "Pride and Prejudice", "Jane Austen", "romance", 1342, "pride_and_prejudice_librivox"),
    pg("sense-and-sensibility", "Sense and Sensibility", "Jane Austen", "romance", 161, "0_sense_and_sensibility_librivox"),
    pg("jane-eyre", "Jane Eyre", "Charlotte Brontë", "romance", 1260, "jane_eyre_librivox", "bronte"),
    pg("persuasion", "Persuasion", "Jane Austen", "romance", 105, "persuasion_0708_librivox"),
    pg("north-and-south", "North and South", "Elizabeth Gaskell", "romance", 4276, "north_and_south_0709_librivox"),
    pg("sherlock-holmes", "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "mystery", 1661, "adventures_holmes",
       "detective"),
    pg("hound-baskervilles", "The Hound of the Baskervilles", "Arthur Conan Doyle", "mystery", 2852,
       "hound_baskervilles_librivox", "sherlock holmes detective"),
    pg("moonstone", "The Moonstone", "Wilkie Collins", "mystery", 155, "moonstone_0802_librivox", "detective"),
    pg("styles", "The Mysterious Affair at Styles", "Agatha Christie", "mystery", 863, None,
       "poirot detective"),  # no LibriVox recording
    pg("time-machine", "The Time Machine", "H. G. Wells", "scifi", 35, "time_machine_0805_librivox"),
    pg("war-of-the-worlds", "The War of the Worlds", "H. G. Wells", "scifi", 36, "war_of_the_worlds_librivox",
       "martians aliens"),
    pg("frankenstein", "Frankenstein", "Mary Shelley", "scifi", 84, "frankenstein_shelley", "horror monster"),
    pg("dracula", "Dracula", "Bram Stoker", "scifi", 345, "dracula_librivox", "horror vampire"),
    pg("journey-center-earth", "A Journey to the Centre of the Earth", "Jules Verne", "scifi", 18857,
       "journey_centre_earth_1108_librivox", "center adventure"),
]

# ---- Movies ---------------------------------------------------------------------------------------------
# Public domain films from the Internet Archive's Feature Films collection, and Creative Commons open movies
# (Blender Studio, Nina Paley). (id, title, year, category, archive.org item, file in it, minutes, keywords).
# The file is pinned because many items hold several cuts or parts; if it ever disappears, the kit picks the
# item's H.264 MP4 instead (that plays in every browser). Add your own with `movies add` (see README).
MOVIE_CATEGORIES = {
    "comedy": "Comedy", "drama": "Drama and family", "mystery": "Mystery and film noir",
    "adventure": "Adventure and westerns", "horror": "Horror and science fiction",
    "open-movies": "Open movies (Creative Commons animation)", "my-movies": "My movies (added by you)",
}
PD_FILM = "Public domain (Internet Archive Feature Films)"


def mv(id, title, year, cat, ia, file, minutes, kw="", license=PD_FILM):
    return dict(id=id, title=title, year=year, cat=cat, ia=ia, file=file, minutes=minutes, kw=kw, license=license)


MOVIES = [
    mv("his-girl-friday", "His Girl Friday", 1940, "comedy", "his_girl_friday", "his_girl_friday.mp4", 92,
       "cary grant screwball"),
    mv("meet-john-doe", "Meet John Doe", 1941, "comedy", "meet_john_doe", "meet_john_doe.mp4", 122,
       "gary cooper frank capra"),
    mv("royal-wedding", "Royal Wedding", 1951, "comedy", "royal_wedding", "royal_wedding.mp4", 93,
       "fred astaire musical dance"),
    mv("my-favorite-brunette", "My Favorite Brunette", 1947, "comedy", "my_favorite_brunette",
       "my_favorite_brunette.mp4", 87, "bob hope"),
    mv("flying-deuces", "The Flying Deuces", 1939, "comedy", "TheFlyingDeuces", "The_Flying_Deuces.mp4", 69,
       "laurel and hardy"),
    mv("the-general", "The General", 1926, "comedy", "The_General_Buster_Keaton", "The_General.mp4", 75,
       "buster keaton silent train"),
    mv("steamboat-bill", "Steamboat Bill, Jr.", 1928, "comedy", "SteamboatBillJr", "Steamboat_Bill.Jr_512kb.mp4", 69,
       "buster keaton silent"),
    mv("one-week", "One Week", 1920, "comedy", "OneWeek", "One_Week_512kb.mp4", 22, "buster keaton silent short"),
    mv("the-immigrant", "The Immigrant", 1917, "comedy", "CC_1917_06_17_TheImmigrant",
       "CC_1917_06_17_TheImmigrant_512kb.mp4", 24, "charlie chaplin silent short"),
    mv("little-princess", "The Little Princess", 1939, "drama", "little_princess", "little_princess.mp4", 93,
       "shirley temple family kids"),
    mv("cyrano", "Cyrano de Bergerac", 1950, "drama", "Cyrano_DeBergerac", "Cyrano_De_Bergerac.mp4", 112,
       "jose ferrer romance"),
    mv("great-expectations", "Great Expectations", 1946, "drama", "GreatExpectations1946", "GreatExpectations1946.mp4",
       118, "dickens david lean"),
    mv("jungle-book", "Jungle Book", 1942, "drama", "JungleBook", "Jungle_Book.mp4", 108, "kipling sabu family kids"),
    mv("gullivers-travels", "Gulliver's Travels", 1939, "drama", "gullivers_travels1939", "gullivers_travels1939.mp4",
       76, "animation cartoon family kids fleischer"),
    mv("dressed-to-kill", "Dressed to Kill (Sherlock Holmes)", 1946, "mystery", "dressed_to_kill",
       "dressed_to_kill.mp4", 72, "sherlock holmes basil rathbone detective"),
    mv("secret-weapon", "Sherlock Holmes and the Secret Weapon", 1943, "mystery", "secret_weapon",
       "sherlock_holmes_and_the_secret_weapon.mp4", 68, "sherlock holmes basil rathbone detective"),
    mv("the-stranger", "The Stranger", 1946, "mystery", "TheStranger_0", "The_Stranger.mp4", 95,
       "orson welles noir"),
    mv("scarlet-street", "Scarlet Street", 1945, "mystery", "ScarletStreet", "Scarlet_Street.mp4", 102,
       "fritz lang noir"),
    mv("suddenly", "Suddenly", 1954, "mystery", "suddenly", "suddenly.mp4", 77, "frank sinatra noir thriller"),
    mv("quicksand", "Quicksand", 1950, "mystery", "Quicksand_clear", "Quicksand.mp4", 79, "mickey rooney noir"),
    mv("lost-world-1925", "The Lost World", 1925, "adventure", "lost_world", "lost_world.mp4", 64,
       "dinosaurs silent conan doyle"),
    mv("iron-mask", "The Iron Mask", 1929, "adventure", "iron_mask", "iron_mask.mp4", 95,
       "douglas fairbanks musketeers dumas"),
    mv("last-of-the-mohicans", "The Last of the Mohicans", 1920, "adventure", "last_of_the_mohicans_1920",
       "last_of_the_mohicans_silent_512kb.mp4", 71, "silent western"),
    mv("20000-leagues", "20,000 Leagues Under the Sea", 1916, "adventure", "20000LeaguesUndertheSea",
       "20000_Leagues_Under_the_Sea_512kb.mp4", 108, "jules verne silent submarine"),
    mv("mclintock", "McLintock!", 1963, "adventure", "mclintok_widescreen", "McLintock_512kb.mp4", 127,
       "john wayne western comedy"),
    mv("night-living-dead", "Night of the Living Dead", 1968, "horror", "Night.Of.The.Living.Dead_1080p",
       "NightOfTheLivingDead.mp4", 96, "zombies george romero"),
    mv("house-haunted-hill", "House on Haunted Hill", 1959, "horror", "house_on_haunted_hill_ipod",
       "house_on_haunted_hill_512kb.mp4", 75, "vincent price ghost"),
    mv("carnival-of-souls", "Carnival of Souls", 1962, "horror", "CarnivalofSouls", "CarnivalOfSouls.mp4", 78, "ghost"),
    mv("little-shop", "The Little Shop of Horrors", 1960, "horror", "TheLittleShopOfHorrors1960",
       "The-Little-Shop-of-Horrors_512kb.mp4", 72, "roger corman jack nicholson comedy"),
    mv("nosferatu", "Nosferatu", 1922, "horror", "Nosferatu1922", "Nosferatu.mp4", 94, "vampire dracula silent",
       "Public domain (CC0, Internet Archive)"),
    mv("phantom-opera", "The Phantom of the Opera", 1925, "horror", "ThePhantomoftheOpera",
       "Phantom_of_the_Opera_512kb.mp4", 106, "lon chaney silent"),
    mv("hunchback", "The Hunchback of Notre Dame", 1923, "horror", "The_Hunchback_of_Notre_Dame",
       "The_Hunchback_of_Notre_Dame_512kb.mp4", 101, "lon chaney silent victor hugo"),
    mv("killers-from-space", "Killers from Space", 1954, "horror", "Killers_from_space", "Killers_from_space.mp4", 71,
       "aliens scifi"),
    mv("sita-sings-the-blues", "Sita Sings the Blues", 2008, "open-movies", "Sita_Sings_the_Blues",
       "Sita_Sings_the_Blues.mp4", 82, "animation nina paley musical", "CC0 (Nina Paley)"),
    mv("big-buck-bunny", "Big Buck Bunny", 2008, "open-movies", "BigBuckBunny_124",
       "Content/big_buck_bunny_720p_surround.mp4", 10, "animation blender kids short", "CC BY 3.0 (Blender Foundation)"),
    mv("elephants-dream", "Elephants Dream", 2006, "open-movies", "ElephantsDream", "ed_hd.mp4", 11,
       "animation blender short", "CC BY 3.0 (Blender Foundation)"),
    mv("sintel", "Sintel", 2010, "open-movies", "Sintel", "sintel-2048-stereo.mp4", 15,
       "animation blender dragon short", "CC BY 3.0 (Blender Foundation)"),
    mv("tears-of-steel", "Tears of Steel", 2012, "open-movies", "Tears-of-Steel", "tears_of_steel_1080p.mp4", 12,
       "blender scifi robots short", "CC BY 3.0 (Blender Foundation)"),
    mv("cosmos-laundromat", "Cosmos Laundromat: First Cycle", 2015, "open-movies", "CosmosLaundromatFirstCycle",
       "Cosmos Laundromat - First Cycle (1080p).mp4", 12, "animation blender sheep short",
       "CC BY 4.0 (Blender Foundation)"),
    mv("caminandes", "Caminandes 1: Llama Drama", 2013, "open-movies", "Caminandes1LlamaDrama",
       "01_llama_drama_1080p.mp4", 2, "animation blender llama kids short", "CC BY 3.0 (Blender Foundation)"),
]
MY_MOVIES = os.path.join(MOVIES_DIR, "my-movies.json")  # films added with `movies add` (content, not in git)
VIDEO_EXT = (".mp4", ".m4v", ".webm", ".mkv", ".avi", ".mov", ".ogv")


def movie_file(m):
    ext = os.path.splitext(m["file"])[1].lower() or ".mp4"
    return os.path.join(MOVIES_DIR, m["cat"], safe(f"{m['title']} ({m['year']})" if m.get("year") else m["title"]) + ext)


def my_movies():
    """Films added with `movies add` (movies/my-movies.json), in the same shape as MOVIES."""
    import json
    try:
        with open(MY_MOVIES, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def all_movies():
    return MOVIES + my_movies()


MOVIE_FIELDS = ("id", "title", "year", "kw", "cat")

# ---- Software ------------------------------------------------------------------------------------------
# Each OS has a list of downloads (label, how to find the newest one), or a "note" when there is no
# download for that OS (Linux users install these from their distribution, which needs internet).
#   ("github", "owner/repo", regex)           asset of the newest GitHub release (checksum checked when GitHub has one)
#   ("page", url, regex)                       first link on that page matching regex
#   ("redirect", url)                          the file that url forwards to (Firefox's "latest" links)
#   ("github-tag", "owner/repo", url)          url with {v} = the newest release's version
# Only official release hosts are allowed (TRUSTED_SOFTWARE_HOSTS): no SourceForge or other download portals,
# which have wrapped installers in adware before. Files are checked against the publisher's sha256 where one is
# posted (GitHub release digests, VideoLAN .sha256, Mozilla SHA256SUMS); software/<os>/<app>/checksums.json records it.
TRUSTED_SOFTWARE_HOSTS = (
    "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",  # GitHub releases
    "get.videolan.org",           # VideoLAN (redirects to its mirror network; checked against videolan.org's sha256)
    "sumatrapdfreader.org",       # SumatraPDF author's site
    "download-installer.cdn.mozilla.net",  # Mozilla
    "buildbot.libretro.com",      # RetroArch (libretro's own build server)
)
CHECKSUMS = "checksums.json"
STALE_DAYS = 120  # the Software page warns when a program was last checked for updates longer ago (4 months)
OS_NAMES = {"windows": "Windows", "mac": "Mac", "linux": "Linux"}
SOFTWARE = [
    dict(id="vlc", name="VLC media player", kw="video audio music movie player media",
         about="Plays almost every video and audio file, DVDs and audio CDs.", license="GPL-2.0",
         os={"windows": [("64-bit installer", ("page", "https://get.videolan.org/vlc/last/win64/", r"vlc-[\d.]+-win64\.exe"))],
             "mac": [("Apple Silicon and Intel", ("page", "https://get.videolan.org/vlc/last/macosx/",
                                                  r"vlc-[\d.]+-universal\.dmg"))],
             "linux": "VLC has no single download for Linux: install it from your distribution "
                      "(sudo apt install vlc, or the Software app) while you still have internet."}),
    dict(id="mplayer", name="MPlayer", kw="video audio player media",
         about="Classic video and audio player. The MPlayer project publishes no Windows or Mac programs, only "
               "source code; the kit offers mpv, its maintained successor, instead.", license="GPL-2.0",
         os={"windows": "No official Windows build (the only ones are unofficial uploads on SourceForge, which the "
                        "kit doesn't use). Use mpv (below), MPlayer's maintained successor, or VLC.",
             "mac": "MPlayer has no current Mac build. Use mpv (below), its modern successor, or VLC.",
             "linux": "Install from your distribution: sudo apt install mplayer (or mpv)."}),
    dict(id="mpv", name="mpv", kw="video audio player media mplayer",
         about="Modern player based on MPlayer: fast, plays everything, keyboard driven.", license="GPL-2.0",
         os={"windows": [("64-bit (zip)", ("github", "mpv-player/mpv", r"mpv-v[\d.]+-x86_64-pc-windows-msvc\.zip"))],
             "mac": [("Apple Silicon", ("github", "mpv-player/mpv", r"mpv-v[\d.]+-macos-15-arm\.zip")),
                     ("Intel", ("github", "mpv-player/mpv", r"mpv-v[\d.]+-macos-15-intel\.zip"))],
             "linux": "Install from your distribution: sudo apt install mpv."}),
    dict(id="calibre", name="Calibre", kw="ebook epub library reader convert books",
         about="E-book library: reads EPUB/PDF, converts between formats, sends books to e-readers.", license="GPL-3.0",
         os={"windows": [("64-bit installer", ("github", "kovidgoyal/calibre", r"calibre-64bit-[\d.]+\.msi"))],
             "mac": [("Apple Silicon and Intel", ("github", "kovidgoyal/calibre", r"calibre-[\d.]+\.dmg"))],
             "linux": [("x86_64 (tar.xz, see calibre-ebook.com/download_linux)",
                        ("github", "kovidgoyal/calibre", r"calibre-[\d.]+-x86_64\.txz"))]}),
    dict(id="sumatrapdf", name="SumatraPDF", kw="pdf epub ebook reader books",
         about="Small, fast reader for PDF, EPUB, MOBI and comic books. Windows only.", license="GPL-3.0",
         os={"windows": [("64-bit installer", ("page", "https://www.sumatrapdfreader.org/download-free-pdf-viewer",
                                               r"/dl/rel/[\d.]+/SumatraPDF-[\d.]+-64-install\.exe"))],
             "mac": "Windows only. On a Mac, Preview opens PDFs and Books opens EPUBs (or use Thorium).",
             "linux": "Windows only. Use Thorium Reader or your distribution's document viewer."}),
    dict(id="thorium", name="Thorium Reader", kw="epub ebook reader books audiobook accessibility",
         about="Easy EPUB reader (also reads PDF and audiobooks), with read-aloud.", license="BSD-3-Clause",
         os={"windows": [("64-bit installer", ("github", "edrlab/thorium-reader", r"Thorium-[\d.]+-x64\.exe"))],
             "mac": [("Apple Silicon", ("github", "edrlab/thorium-reader", r"Thorium-[\d.]+-arm64\.dmg")),
                     ("Intel", ("github", "edrlab/thorium-reader", r"Thorium-[\d.]+-x64\.dmg"))],
             "linux": [("x86_64 AppImage", ("github", "edrlab/thorium-reader", r"Thorium-[\d.]+-x86_64\.AppImage")),
                       ("x86_64 .deb", ("github", "edrlab/thorium-reader", r"Thorium-[\d.]+-amd64\.deb"))]}),
    dict(id="7zip", name="7-Zip", kw="zip 7z archive unzip compress extract",
         about="Opens and makes .zip, .7z, .rar, .tar and more archives.", license="LGPL-2.1",
         os={"windows": [("64-bit installer", ("github", "ip7z/7zip", r"7z\d+-x64\.exe"))],
             "mac": [("command line (7zz), Apple Silicon and Intel", ("github", "ip7z/7zip", r"7z\d+-mac\.tar\.xz"))],
             "linux": [("command line (7zz), x86_64", ("github", "ip7z/7zip", r"7z\d+-linux-x64\.tar\.xz"))]}),
    dict(id="firefox", name="Firefox", kw="web browser internet",
         about="Web browser (English, US). Opens the kit's pages and PDFs too.", license="MPL-2.0",
         os={"windows": [("64-bit installer", ("redirect",
                                               "https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US"))],
             "mac": [("Apple Silicon and Intel", ("redirect",
                                                  "https://download.mozilla.org/?product=firefox-latest-ssl&os=osx&lang=en-US"))],
             "linux": [("x86_64 (tar.xz)", ("redirect",
                                            "https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US"))]}),
    dict(id="retroarch", name="RetroArch", kw="games emulator retro arcade",
         about="Front end for game emulators. Cores (the emulators) are downloaded inside the app, which needs "
               "internet; the Windows and Linux bundles here include a cores pack.", license="GPL-3.0",
         os={"windows": [("64-bit installer", ("github-tag", "libretro/RetroArch",
                                               "https://buildbot.libretro.com/stable/{v}/windows/x86_64/RetroArch-Win64-setup.exe")),
                         ("cores pack (7z)", ("github-tag", "libretro/RetroArch",
                                              "https://buildbot.libretro.com/stable/{v}/windows/x86_64/RetroArch_cores.7z"))],
             "mac": [("Apple Silicon and Intel", ("github-tag", "libretro/RetroArch",
                                                  "https://buildbot.libretro.com/stable/{v}/apple/osx/universal/RetroArch_Metal.dmg"))],
             "linux": [("x86_64 AppImage (7z)", ("github-tag", "libretro/RetroArch",
                                                 "https://buildbot.libretro.com/stable/{v}/linux/x86_64/RetroArch.7z")),
                       ("cores pack (7z)", ("github-tag", "libretro/RetroArch",
                                            "https://buildbot.libretro.com/stable/{v}/linux/x86_64/RetroArch_cores.7z"))]}),
    dict(id="notepadpp", name="Notepad++", kw="text editor code notepad",
         about="Text and code editor. Windows only.", license="GPL-3.0",
         os={"windows": [("64-bit installer", ("github", "notepad-plus-plus/notepad-plus-plus",
                                               r"npp\.[\d.]+\.Installer\.x64\.exe"))],
             "mac": "Windows only. On a Mac use TextEdit, or BBEdit / CotEditor (not in the kit).",
             "linux": "Windows only. Use your distribution's text editor (gedit, Kate, nano)."}),
]


# ---- Where things go, and what's installed -------------------------------------------------------------
def safe(s):
    return re.sub(r'[<>:"/\\|?*]+', "", s).strip(" .")


def book_name(b):
    return safe(f"{b['title']} - {b['author']}")


def book_file(b, fmt):
    """books/<category>/<Title - Author>.<fmt> (a folder for books that come one chapter per file)."""
    if b.get("pdf_index"):
        return os.path.join(BOOKS_DIR, b["cat"], book_name(b))
    return os.path.join(BOOKS_DIR, b["cat"], f"{book_name(b)}.{fmt}")


def audio_dir(b):
    return os.path.join(AUDIO_DIR, b["cat"], book_name(b))


DONE = "_complete.txt"  # written into a folder once every file of it is downloaded
TRACKS = "_tracks.json"  # audiobook folder: {mp3 file: chapter title}


def formats_of(b):
    if b.get("zim"):
        return ["library"]
    if b.get("gutenberg"):
        return ["epub"]
    if b.get("openstax") or b.get("pdf_index"):
        return ["pdf"]
    return [f for f in ("epub", "pdf") if f in b.get("files", {})]


def visible(folder):
    try:
        return sorted(f for f in os.listdir(folder) if not f.startswith(".") and f != DONE)
    except OSError:
        return []


def book_status(b):
    """{"epub": path, "pdf": path, "library": zim name, "audio": [mp3 paths]} for what's on disk."""
    have = {}
    if b.get("zim"):
        pat = re.compile(re.escape(b["zim"][1]) + r"\d{4}-\d{2}\.zim$")
        zims = [f for f in visible(os.path.join(KIT, "kiwix")) if pat.match(f)]
        if zims:
            have["library"] = zims[-1][:-4]
    for fmt in formats_of(b):
        p = book_file(b, fmt)
        if fmt != "library" and (os.path.isfile(p) or os.path.isfile(os.path.join(p, DONE))):
            have[fmt] = p
    a = audio_dir(b)
    if os.path.isfile(os.path.join(a, DONE)):
        have["audio"] = [os.path.join(a, f) for f in visible(a) if f.lower().endswith(".mp3")]
    return have


def software_files(app, os_name):
    """Downloaded files for one app and OS: software/<os>/<app id>/<file>."""
    d = os.path.join(SOFTWARE_DIR, os_name, app["id"])
    return [os.path.join(d, f) for f in visible(d) if not f.endswith((".part", ".json"))]


# ---- Picking by words -----------------------------------------------------------------------------------
def pick(items, words, fields):
    """Items matching any of the words: 'all', a group (textbooks, fiction), a category, an id, or a keyword
    found in the title/author/keywords. Returns (matches in catalog order, words that matched nothing)."""
    chosen, unknown = [], []
    for raw in words:
        for w in [x.strip() for x in raw.lower().split(",") if x.strip()]:
            if w == "all":
                hit = list(items)
            else:
                hit = [i for i in items if w == i["id"] or w == i.get("cat")
                       or (w in GROUPS and CATEGORIES.get(i.get("cat"), ("", ""))[1] == w)]
                if not hit:  # keyword or phrase: every word of "think python" (or think-python) must appear
                    parts = w.replace("-", " ").split()
                    hit = [i for i in items if all(p in " ".join(str(i.get(f, "")) for f in fields).lower()
                                                   for p in parts)]
            if not hit:
                unknown.append(w)
            chosen += [i for i in hit if i not in chosen]
    order = {id(i): n for n, i in enumerate(items)}
    return sorted(chosen, key=lambda i: order[id(i)]), unknown


BOOK_FIELDS = ("id", "title", "author", "kw", "cat")
SOFTWARE_FIELDS = ("id", "name", "kw", "about")


# ---- Your own folders (Settings page on the hub) --------------------------------------------------------
# kit-settings.json in the kit folder: {"folders": {"movies": [path, ...], "books": [path, ...]}}. Read when the hub
# starts and saved by its Settings page. It belongs to one computer, so make-drive doesn't copy it to the stick.
SETTINGS_FILE = os.path.join(KIT, "kit-settings.json")
FOLDER_KINDS = {"movies": "Movies", "books": "Books and audiobooks"}
BOOK_EXT = (".epub", ".pdf", ".mobi", ".azw3", ".fb2", ".djvu", ".cbz", ".cbr", ".txt", ".rtf", ".docx", ".html", ".htm")
AUDIO_EXT = (".mp3", ".m4b", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav")


def load_settings():
    import json
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    folders = s.get("folders") if isinstance(s.get("folders"), dict) else {}
    s["folders"] = {k: [p for p in folders.get(k, []) if isinstance(p, str) and p.strip()] for k in FOLDER_KINDS}
    return s


def save_settings(s):
    import json
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    os.replace(tmp, SETTINGS_FILE)


def _volume(p):
    """The drive a path is on: 'E:' on Windows, '/Volumes/NAME' for a Mac external drive, '' for the Mac's own disk."""
    d = os.path.splitdrive(p)[0]
    if d:
        return d.lower()
    parts = p.split(os.sep)
    return os.sep.join(parts[:3]) if len(parts) > 2 and parts[1] == "Volumes" else ""


def store_folder(path):
    """How a folder is written to kit-settings.json. A folder on the same thumb drive as the kit is saved relative to
    the kit (..\\Movies), so it is still found when Windows gives the drive another letter."""
    path = os.path.abspath(os.path.expanduser(path))
    v = _volume(path)
    return os.path.relpath(path, KIT) if v and v == _volume(KIT) else path


def resolve_folder(stored):
    return os.path.normpath(os.path.join(KIT, os.path.expanduser(stored)))
