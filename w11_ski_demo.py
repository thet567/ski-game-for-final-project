import random
import time
import curses
from collections import deque

FPS = 30
MIN_COLUMNS = 64
MIN_LINES = 21
MAX_FIELD_WIDTH = 68
FIELD_TOP = 3

STATUS_READY = "READY"
STATUS_PLAYING = "PLAYING"
STATUS_PAUSED = "PAUSED"
STATUS_GAME_OVER = "GAME_OVER"

BASE_SPEED = 3.0


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def create_state(field_width, field_height, rng):
    half_width = min(19, max(13, (field_width - 12) // 2))

    state = {
        "status": STATUS_READY,
        "x": field_width // 2,
        "y": max(3, int(field_height * 0.35)),
        "direction": 1,
        "speed": 1.0,
        "elapsed_time": 0.0,
        "scroll_count": 0,
        "score": 0,
        "level": 1,
        "scroll_progress": 0.0,
        "field_width": field_width,
        "field_height": field_height,
        "course_center": field_width // 2,
        "course_half_width": half_width,
        "rows": deque(),
        "game_over_reason": ""
    }

    for _ in range(field_height):
        state["rows"].append(
            create_course_row(state, rng, with_tree=False)
        )

    return state


def create_course_row(state, rng, with_tree=True):
    width = state["field_width"]
    half = state["course_half_width"]

    if rng.random() < 0.13:
        half = int(clamp(
            half + rng.choice([-1, 1]), 13, 21
        ))

    center = state["course_center"] + rng.choice(
        [-1, 0, 0, 0, 0, 1]
    )

    center = int(clamp(
        center, half + 3, width - half - 4
    ))

    state["course_center"] = center
    state["course_half_width"] = half

    left = center - half
    right = center + half

    tree = None
    stone = None

    tree_rate = min(
        0.52, 0.23 + (state["level"] - 1) * 0.055
    )

    # 木の生成
    if with_tree and rng.random() < tree_rate:
        tree = rng.randint(left + 3, right - 3)

    # 改良機能01：石の追加
    if with_tree and rng.random() < 0.15:
        stone = rng.randint(left + 3, right - 3)

        if stone == tree:
            stone = None

    return {
        "left": left,
        "right": right,
        "tree": tree,
        "stone": stone
    }


def update_distance_score(state):
    state["score"] += 1


def move_course_one_row(state, rng):
    state["rows"].pop()

    state["rows"].appendleft(
        create_course_row(state, rng)
    )

    state["x"] += state["direction"]
    state["scroll_count"] += 1

    state["level"] = state["scroll_count"] // 100 + 1

    update_distance_score(state)


def check_collision(state):
    player_x = int(round(state["x"]))
    row = state["rows"][state["y"]]

    # 森の端に衝突
    if player_x <= row["left"] or player_x >= row["right"]:
        state["game_over_reason"] = "FOREST!"
        state["status"] = STATUS_GAME_OVER

    # 木に衝突
    elif row["tree"] == player_x:
        state["game_over_reason"] = "TREE!"
        state["status"] = STATUS_GAME_OVER

    # 改良機能01：石との衝突判定
    elif row["stone"] == player_x:
        state["game_over_reason"] = "STONE!"
        state["status"] = STATUS_GAME_OVER


def update_game(state, dt, rng):
    if state["status"] != STATUS_PLAYING:
        return

    state["elapsed_time"] += dt

    state["scroll_progress"] += (
        BASE_SPEED * state["speed"] * dt
    )

    while (
        state["scroll_progress"] >= 1.0
        and state["status"] == STATUS_PLAYING
    ):
        state["scroll_progress"] -= 1.0

        move_course_one_row(state, rng)
        check_collision(state)


def read_key(state, key):
    if key in (ord("q"), ord("Q")):
        return "QUIT"

    if state["status"] == STATUS_GAME_OVER:
        if key in (ord("r"), ord("R")):
            return "RESTART"

    if key == ord(" "):
        if state["status"] in (
            STATUS_READY, STATUS_PAUSED
        ):
            state["status"] = STATUS_PLAYING

        elif state["status"] == STATUS_PLAYING:
            state["status"] = STATUS_PAUSED

        return None

    if state["status"] == STATUS_PLAYING:
        if key == curses.KEY_LEFT:
            state["direction"] = -1

        elif key == curses.KEY_RIGHT:
            state["direction"] = 1

    return None


def draw_line(screen, y, text, style=0):
    rows, cols = screen.getmaxyx()

    if 0 <= y < rows - 1 and cols >= 2:
        screen.addnstr(
            y, 1, str(text), cols - 2, style
        )


def draw_game(screen, state):
    screen.erase()

    rows, cols = screen.getmaxyx()
    width = state["field_width"]
    offset = (cols - width) // 2

    draw_line(
        screen,
        0,
        "========== SNOW FOREST ADVENTURE ==========",
        curses.A_BOLD
    )

    hud = (
        f"LV {state['level']:02d} | "
        f"SCORE {state['score']:05d} | "
        f"SPEED {state['speed']:.1f}x"
    )

    draw_line(screen, 1, hud, curses.A_BOLD)

    screen.addnstr(2, offset, "=" * width, width)

    player_x = int(round(state["x"]))

    for i, row in enumerate(state["rows"]):
        chars = [" "] * width

        # 左側の森
        for x in range(row["left"] + 1):
            chars[x] = "*"

        # 右側の森
        for x in range(row["right"], width):
            chars[x] = "*"

        # 木
        if row["tree"] is not None:
            chars[row["tree"]] = "*"

        # 改良機能01：石の表示
        if row["stone"] is not None:
            chars[row["stone"]] = "#"

        # プレイヤー
        if i == state["y"] and 0 <= player_x < width:
            if state["status"] == STATUS_GAME_OVER:
                chars[player_x] = "X"
            else:
                chars[player_x] = "O"

        screen.addnstr(
            FIELD_TOP + i,
            offset,
            "".join(chars),
            width
        )

    if state["status"] == STATUS_READY:
        message = "READY! Press SPACE to start"

    elif state["status"] == STATUS_PAUSED:
        message = "PAUSED - Press SPACE to resume"

    elif state["status"] == STATUS_GAME_OVER:
        message = (
            f"GAME OVER ({state['game_over_reason']})"
            " - R to restart"
        )

    else:
        message = "Avoid trees and stones!"

    draw_line(
        screen,
        rows - 3,
        message,
        curses.A_BOLD
    )

    draw_line(
        screen,
        rows - 2,
        "LEFT/RIGHT: Move | SPACE: Pause | R: Restart | Q: Quit"
    )

    screen.refresh()


def run(screen):
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    screen.keypad(True)
    screen.nodelay(True)

    rng = random.Random()
    state = None
    current_size = None
    last_time = time.monotonic()

    while True:
        now = time.monotonic()
        dt = min(0.10, now - last_time)
        last_time = now

        height, width = screen.getmaxyx()
        key = screen.getch()

        if key in (ord("q"), ord("Q")):
            break

        if width < MIN_COLUMNS or height < MIN_LINES:
            screen.erase()

            draw_line(
                screen,
                1,
                f"Terminal too small: {width}x{height}"
            )

            draw_line(
                screen,
                3,
                f"Please enlarge to {MIN_COLUMNS}x{MIN_LINES}"
            )

            screen.refresh()

            state = None
            current_size = None

            time.sleep(1.0 / FPS)
            continue

        size = (height, width)

        if state is None or size != current_size:
            field_width = min(MAX_FIELD_WIDTH, width - 4)
            field_height = height - 7

            state = create_state(
                field_width,
                field_height,
                rng
            )

            current_size = size

        command = read_key(state, key)

        if command == "QUIT":
            break

        if command == "RESTART":
            state = create_state(
                state["field_width"],
                state["field_height"],
                rng
            )

            state["status"] = STATUS_PLAYING

        update_game(state, dt, rng)
        draw_game(screen, state)

        time.sleep(1.0 / FPS)


def main():
    try:
        curses.wrapper(run)

    except curses.error as error:
        print("Please run this game in the VS Code terminal.")
        print(f"Error: {error}")


if __name__ == "__main__":
    main()