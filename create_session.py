from telethon.sync import TelegramClient
import os

# --- ĐIỀN THÔNG TIN CỦA BẠN VÀO ĐÂY ---
api_id = 'xxxxxxxxxxxxxx'          # Thay bằng api_id của bạn
api_hash = 'xxxxxxxxxxxxxxxx' # Thay bằng api_hash của bạn
phone_number = '+xxxxxxxxxxxxxxxxxxxx'     
session_name = 'xxxxxxxxxxxxxxxxxxxx'

def create_session():
    print(f"--- Đang khởi tạo phiên đăng nhập cho {phone_number} ---")
    
    # Khởi tạo Client
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        # Cách này sẽ tự động handle việc hỏi mã OTP và Password 2FA tại CMD
        client.start(phone=phone_number)
        
        if client.is_user_authorized():
            print("\n" + "="*30)
            print("THÀNH CÔNG RỒI!")
            print(f"File '{session_name}.session' đã được tạo.")
            me = client.get_me()
            print(f"Đã đăng nhập tài khoản: {me.first_name}")
            print("="*30)
            
    except Exception as e:
        print(f"\n[LỖI]: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    create_session()
