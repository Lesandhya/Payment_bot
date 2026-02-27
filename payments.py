import razorpay
import qrcode
from io import BytesIO
import config

class PaymentProcessor:
    def __init__(self):
        """Razorpay କ୍ଲାଏଣ୍ଟ ଆରମ୍ଭ କରନ୍ତୁ"""
        self.client = razorpay.Client(
            auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)
        )
    
    def create_order(self, amount):
        """ନୂଆ ପେମେଣ୍ଟ ଅର୍ଡର ତିଆରି କରନ୍ତୁ"""
        # ଟଙ୍କାକୁ ପଇସାରେ ପରିଣତ କରନ୍ତୁ (ଗୁଣନ 100)
        amount_paise = int(amount * 100)
        
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1
        }
        
        order = self.client.order.create(data=order_data)
        return order
    
    def generate_qr_code(self, payment_link):
        """ପେମେଣ୍ଟ ଲିଙ୍କ ପାଇଁ QR କୋଡ୍ ତିଆରି କରନ୍ତୁ"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(payment_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # BytesIO ରେ ସେଭ୍ କରନ୍ତୁ
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return img_buffer
    
    def verify_payment(self, order_id, payment_id, signature):
        """ପେମେଣ୍ଟ ସଠିକ୍ କି ନାହିଁ ଯାଞ୍ଚ କରନ୍ତୁ"""
        try:
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            self.client.utility.verify_payment_signature(params_dict)
            return True
        except:
            return False
    
    def fetch_payment(self, payment_id):
        """ପେମେଣ୍ଟ ବିବରଣୀ ଆଣନ୍ତୁ"""
        return self.client.payment.fetch(payment_id)
    
    def fetch_order(self, order_id):
        """ଅର୍ଡର ବିବରଣୀ ଆଣନ୍ତୁ"""
        return self.client.order.fetch(order_id)

# Payment processor object
payment_processor = PaymentProcessor()
