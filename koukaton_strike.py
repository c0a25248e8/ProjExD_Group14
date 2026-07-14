import math
import os
import sys
import pygame as pg

WIDTH = 1100  # ゲームウィンドウの幅
HEIGHT = 650  # ゲームウィンドウの高さ
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def check_bound(obj_rct: pg.Rect) -> tuple[int, int]:
    """
    オブジェクトが画面の壁に衝突しているかを判定し、反射係数を返す関数
    """
    yoko, tate = 1, 1
    if obj_rct.left < 0 or WIDTH < obj_rct.right:
        yoko = -1
    if obj_rct.top < 0 or HEIGHT < obj_rct.bottom:
        tate = -1
    return yoko, tate


class Bird(pg.sprite.Sprite):
    """
    ゲームキャラクター（こうかとん）に関するクラス
    """
    def __init__(self, num: int, xy: tuple[int, int], name: str):
        super().__init__()
        self.name = name  # 識別用の名前 ("こうかとん1" または "こうかとん2")
        self.base_img = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 1.2)
        self.image = self.base_img
        self.rect = self.image.get_rect()
        self.rect.center = xy

        self.vx = 0.0
        self.vy = 0.0
        self.friction = 0.98

        self.is_dragging = False
        self.max_drag_dist = 200  
        self.has_shot = False  # このターンで既に発射されたかどうかのフラグ

        self.has_triggered_combo = False  # [追加]このターンに愛情コンボを発動したか

    def update(self, screen: pg.Surface, is_my_turn: bool):
        """
        こうかとんの移動、壁での跳ね返り、および自分のターン時のドラッグ矢印描画
        """
        if not self.is_dragging:
            self.rect.move_ip(self.vx, self.vy)

            yoko, tate = check_bound(self.rect)
            if yoko == -1:
                self.vx *= -1
                if self.rect.left < 0: self.rect.left = 0
                if self.rect.right > WIDTH: self.rect.right = WIDTH
            if tate == -1:
                self.vy *= -1
                if self.rect.top < 0: self.rect.top = 0
                if self.rect.bottom > HEIGHT: self.rect.bottom = HEIGHT

            self.vx *= self.friction
            self.vy *= self.friction
            
            # 停止判定
            if math.hypot(self.vx, self.vy) < 0.1:
                self.vx, self.vy = 0.0, 0.0

        # 自分のターン、かつドラッグ中のみガイドラインを描画
        if is_my_turn and self.is_dragging:
            mouse_pos = pg.mouse.get_pos()
            dx = mouse_pos[0] - self.rect.centerx
            dy = mouse_pos[1] - self.rect.centery
            dist = math.hypot(dx, dy)
            
            if dist > self.max_drag_dist:
                dx = (dx / dist) * self.max_drag_dist
                dy = (dy / dist) * self.max_drag_dist
            
            target_x = self.rect.centerx - dx
            target_y = self.rect.centery - dy
            
            pg.draw.line(screen, (255, 0, 0), self.rect.center, (target_x, target_y), 5)
            
            current_drag_x = self.rect.centerx + dx
            current_drag_y = self.rect.centery + dy
            pg.draw.line(screen, (0, 0, 255), self.rect.center, (current_drag_x, current_drag_y), 2)
            pg.draw.circle(screen, (0, 0, 255), (int(current_drag_x), int(current_drag_y)), 8)

        screen.blit(self.image, self.rect)

        # 自分のターンであることの目印（足元に黄色い円を描画）
        if is_my_turn:
            pg.draw.circle(screen, (255, 255, 0), self.rect.center, self.rect.width // 2 + 5, 2)


class Enemy(pg.sprite.Sprite):
    """
    敵キャラクター（スライム）に関するクラス
    """
    def __init__(self, xy: tuple[int, int]):
        super().__init__()
        self.image = pg.transform.rotozoom(pg.image.load("fig/suraimu.png"), 0, 0.2)
        self.rect = self.image.get_rect()
        self.rect.center = xy
        
        self.max_hp = 5  # こうかとんが2体になったのでHPを少し多めの 5 に変更
        self.hp = self.max_hp

    def update(self, screen: pg.Surface):
        """
        敵の描画とHPバーの描画を行う
        """
        screen.blit(self.image, self.rect)

        # HPバーの描画
        if self.hp > 0:
            bar_width = 30  
            bar_height = 5
            bar_x = self.rect.centerx - bar_width // 2
            bar_y = self.rect.top - 8  
            
            pg.draw.rect(screen, (255, 0, 0), (bar_x, bar_y, bar_width, bar_height))
            hp_ratio = self.hp / self.max_hp
            pg.draw.rect(screen, (0, 255, 0), (bar_x, bar_y, int(bar_width * hp_ratio), bar_height))


def main():
    pg.display.set_caption("こうかとんストライク（2人交互ターン制）")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    bg_img = pg.image.load(f"fig/senjou.png")
    font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 30)  # ターン表示用のフォント

    # BGMの設定と再生
    pg.mixer.music.load("bgm.mp3")            
    pg.mixer.music.play(loops=-1)            

    # --- 変更点: こうかとんを2体作成してリストで管理 ---
    birds = [
        Bird(3, (WIDTH // 4, HEIGHT // 3), "プレイヤー1"),   # 上側に配置
        Bird(1, (WIDTH // 4, HEIGHT * 2 // 3), "プレイヤー2") # 下側に配置（別の画像番号1に設定）
    ]
    turn_idx = 0  # 現在のターン（0: プレイヤー1, 1: プレイヤー2）
    
    # 敵をグループで管理
    enemies = pg.sprite.Group()
    enemy = Enemy((WIDTH * 3 // 4, HEIGHT // 4))
    enemies.add(enemy)
    # ビームのエフェクトを管理するリスト [始点, 終点, 残り表示フレーム数]

    beams = []

    clock = pg.time.Clock()
    
    while True:
        current_bird = birds[turn_idx]  # 現在のターンのこうかとん
        
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.mixer.music.stop()
                return 0
            
            # 現在のターンのこうかとんだけが操作を受け付ける
            if event.type == pg.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if current_bird.rect.collidepoint(event.pos) and not current_bird.has_shot:
                        current_bird.is_dragging = True
                        current_bird.vx, current_bird.vy = 0.0, 0.0

            if event.type == pg.MOUSEBUTTONUP:
                if event.button == 1 and current_bird.is_dragging:
                    current_bird.is_dragging = False
                    current_bird.has_shot = True  # 発射フラグを立てる
                    mouse_pos = event.pos
                    
                    dx = mouse_pos[0] - current_bird.rect.centerx
                    dy = mouse_pos[1] - current_bird.rect.centery
                    dist = math.hypot(dx, dy)
                    
                    if dist > current_bird.max_drag_dist:
                        dx = (dx / dist) * current_bird.max_drag_dist
                        dy = (dy / dist) * current_bird.max_drag_dist
                    
                    current_bird.vx = -dx * 0.25
                    current_bird.vy = -dy * 0.25

        # --- 【追加】味方同士の衝突判定（愛情コンボ） ---
        if current_bird.has_shot and not current_bird.has_triggered_combo:
            # もう一方の待機しているこうかとんを取得
            other_bird = birds[1] if turn_idx == 0 else birds[0]
            
            if current_bird.rect.colliderect(other_bird.rect):
                current_bird.has_triggered_combo = True  # 1ターンに1回のみに制限
                
                # ぶつかったら少し跳ね返る（めり込み防止）
                current_bird.vx *= -0.5
                current_bird.vy *= -0.5
                
                # すべての敵に向けて、待機側のこうかとんから愛情ビームを放つ
                for en in enemies:
                    en.hp -= 2  # 友情コンボによるダメージ
                    # ビームの情報を追加 [始点, 終点, 表示時間(12フレーム)]
                    beams.append([other_bird.rect.center, en.rect.center, 12])
                    
                    if en.hp <= 0:
                        en.kill()

        # --- ターン切り替えロジック ---
        # 動かしたこうかとんが発射済み、かつ完全に静止したらターンを交代
        if current_bird.has_shot and current_bird.vx == 0.0 and current_bird.vy == 0.0:
            current_bird.has_shot = False  # フラグをリセット

            current_bird.has_triggered_combo = False  # 愛情フラグをリセット

            turn_idx = (turn_idx + 1) % len(birds)  # 0と1を交互に切り替え

        # 衝突判定の処理（2体とも敵とぶつかる可能性があるためループで処理）
        for bird in birds:
            for en in enemies:
                if bird.rect.colliderect(en.rect):
                    en.hp -= 1
                    
                    if math.hypot(bird.vx, bird.vy) > 0.5:
                        bird.vx *= -0.5
                        bird.vy *= -0.5
                    
                    if en.hp <= 0:
                        en.kill()

        # 描画処理
        screen.blit(bg_img, [0, 0])
        
        # こうかとんの更新と描画（引数に自分のターンかどうかの真偽値を渡す）
        for i, bird in enumerate(birds):
            bird.update(screen, is_my_turn=(i == turn_idx))
            
        enemies.update(screen)

        # --- 【追加】愛情コンボビームの更新と描画 ---
        for beam in beams[:]:
            start_pos, end_pos, timer = beam
            # レーザーのデザイン
            pg.draw.line(screen, (255, 255, 0), start_pos, end_pos, 14)  # 外側の光（黄色）
            pg.draw.line(screen, (255, 255, 255), start_pos, end_pos, 4) # 内側の芯（白）
            
            beam[2] -= 1  # 残りフレーム数を減らす
            if beam[2] <= 0:
                beams.remove(beam)  # タイマーが切れたら削除
        
        # 画面上部に現在のターンを表示
        turn_text = font.render(f"現在のターン: {birds[turn_idx].name}", True, (255, 255, 255))
        screen.blit(turn_text, (20, 20))
        
        pg.display.update()
        clock.tick(50)


if __name__ == "__main__":
    pg.init()
    pg.mixer.init() 
    main()
    pg.quit()
    sys.exit()